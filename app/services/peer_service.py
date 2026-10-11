"""双站互连：让对方站上的内容，出现在自己站的门口。

这个项目的设定是「两个人都得跑同一套系统」，所以两个人的站是两台
独立的机器，各有各的数据库。问题随之而来：

- 我看不到 TA 那边发的瞬间，除非她也在我这台机器上写；
- 「下次一起出发」这种日子，写在谁那边就只有谁能看见。

这里做三件事：

1. **连接**：绑定握手的时候顺手记下对方站点地址，两台机器各自拉一次
   心跳就算连上了。连上之后可以随时断开重连，不影响已经焊死的关系。
2. **代理**：对方站点上的图片，通过本机 `/couple/images/<缓存名>` 转发过来。
   直接往页面里塞对方域名的问题：浏览器在 HTTPS 页面里会被拦、图片
   地址会过期、对方换域名就全挂。走本机转发，只认缓存下来的那份。
3. **镜像**：把对方的内容复制一份到自己库里（带来源标记），离线也看得见。

关于「互相绑定 + 永生永世」：那些规则在 couple_service 里，和这里无关。
互连只是「让两边互相看得见」，断开互连不会、也不可能解开关系。
"""
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import current_app

from app.extensions import db
from app.models import (
    Couple, MirrorEntry, Moment, PeerConnection, Post, SiteSetting, Vow,
)
from app.models.mixins import utcnow

#: 对方站给的图片不能超过这个大小，否则拒收（防止有人塞个大文件过来）
MAX_IMAGE_BYTES = 5 * 1024 * 1024
REQUEST_TIMEOUT = 6


class PeerError(Exception):
    """互连过程中的业务错误。"""


# --------------------------------------------------------------------------
# 连接
# --------------------------------------------------------------------------
def normalize_url(url: str) -> str:
    """把用户填的地址收拾成规范形式：补 scheme、去尾斜杠、去路径。"""
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    if not p.netloc:
        raise PeerError("这不像一个站点地址")
    return f"{p.scheme}://{p.netloc}"


def _local_peer_token() -> str:
    """本机用来证明「我是 TA 的另一半」的令牌。

    用站点地址 + SECRET_KEY 派生，双方都在后台把对方的令牌填进来即可。
    不做公网鉴权（要求两台机器互相能访问就已经够门槛了），
    但这个令牌能挡住「随便一个路人往 /peer/sync 里灌数据」。
    """
    site = SiteSetting.get("site_url", "") or ""
    raw = f"peer|{site}|{current_app.config['SECRET_KEY'][:24]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def connection() -> PeerConnection | None:
    return PeerConnection.query.first()


def is_connected(conn: PeerConnection | None = None) -> bool:
    conn = conn or connection()
    return bool(conn and conn.is_connected and conn.enabled)


def connect(partner_url: str, partner_token: str = "") -> PeerConnection:
    """建立互连。会先拉一次对方的心跳确认「那台机器上确实跑着这套系统且已绑定」。"""
    url = normalize_url(partner_url)
    if not url:
        raise PeerError("请填对方的站点地址")

    home = SiteSetting.get("site_url", "") or ""
    if home and normalize_url(home) == url:
        raise PeerError("这是你自己的站点地址")

    info = fetch_peer(url)
    if not info.get("ok"):
        raise PeerError(info.get("message") or "对方站点没有应答")
    if not info.get("bound"):
        raise PeerError("对方站点还没有绑定情侣关系")

    conn = connection() or PeerConnection()
    conn.partner_url = url
    conn.partner_name = info.get("name") or ""
    conn.partner_names = "、".join(
        m.get("nickname", "") for m in (info.get("members") or []) if m.get("nickname")
    )
    conn.partner_site = info.get("site") or ""
    conn.partner_token = (partner_token or "").strip()
    conn.partner_sealed = bool(info.get("sealed"))
    conn.enabled = True
    conn.status = "ok"
    conn.last_error = ""
    conn.last_seen_at = utcnow()
    db.session.add(conn)
    db.session.commit()
    return conn


def disconnect() -> bool:
    """断开互连。

    只清连接，不动已经镜像下来的内容 —— 那些内容现在是自己的了。
    关系本身更不受影响：断开互连和「解绑」是两件事。
    """
    conn = connection()
    if conn is None:
        return False
    conn.enabled = False
    conn.status = "off"
    conn.last_error = ""
    db.session.commit()
    return True


def heartbeat() -> PeerConnection:
    """探一次对方站点，更新状态。"""
    conn = connection()
    if conn is None:
        raise PeerError("还没有建立互连")
    info = fetch_peer(conn.partner_url)
    if info.get("ok") and info.get("bound"):
        conn.status = "ok"
        conn.last_error = ""
        conn.last_seen_at = utcnow()
        conn.partner_name = info.get("name") or conn.partner_name
        conn.partner_sealed = bool(info.get("sealed"))
    else:
        conn.status = "error"
        conn.last_error = info.get("message") or "对方站点没有应答"
    db.session.commit()
    return conn


# --------------------------------------------------------------------------
# 对外请求（读对方站）
# --------------------------------------------------------------------------
def fetch_peer(url: str) -> dict:
    try:
        resp = requests.get(f"{url.rstrip('/')}/couple/api/info", timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return {"ok": False, "message": f"对方返回 {resp.status_code}"}
        data = resp.json()
        data["ok"] = True
        return data
    except requests.RequestException as exc:
        return {"ok": False, "message": f"连不上：{exc.__class__.__name__}"}
    except ValueError:
        return {"ok": False, "message": "对方返回的不是 JSON，可能不是本系统"}


# --------------------------------------------------------------------------
# 同步对方内容
# --------------------------------------------------------------------------
def _headers(conn: PeerConnection) -> dict:
    return {"X-LYF-Peer": conn.partner_token or _local_peer_token()}


def sync(source: str = "manual") -> dict:
    """拉一次对方的内容。

    只记新增，不覆盖已有的 —— 镜像内容是别人家的东西，只读不改。
    """
    conn = connection()
    if conn is None or not conn.enabled:
        raise PeerError("还没有建立互连")

    base = conn.partner_url.rstrip("/")
    stats = {"moments": 0, "posts": 0, "vows": 0, "anniversaries": 0}

    plan = [
        ("moments", f"{base}/couple/peer/moments", _mirror_moment),
        ("posts", f"{base}/couple/peer/posts", _mirror_post),
        ("vows", f"{base}/couple/peer/vows", _mirror_vow),
        ("anniversaries", f"{base}/couple/peer/anniversaries", _mirror_anniversary),
    ]
    for key, url, handler in plan:
        try:
            resp = requests.get(url, headers=_headers(conn), timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue
            payload = resp.json()
        except (requests.RequestException, ValueError):
            continue
        for row in payload.get("rows") or []:
            if handler(conn, row):
                stats[key] += 1

    conn.last_sync_at = utcnow()
    conn.status = "ok"
    conn.last_error = ""
    db.session.commit()
    return stats


def _existing(kind: str, remote_id) -> MirrorEntry | None:
    return MirrorEntry.query.filter_by(kind=kind, remote_id=str(remote_id)).first()


def _mirror_moment(conn: PeerConnection, row: dict) -> bool:
    remote_id = row.get("id")
    if remote_id is None or _existing("moment", remote_id):
        return False

    entry = MirrorEntry(
        kind="moment",
        remote_id=str(remote_id),
        title=(row.get("content") or "")[:80],
        author=row.get("author") or "",
        payload_json=json.dumps(row, ensure_ascii=False),
        published_at=_parse_dt(row.get("created_at")),
    )
    entry.image_url = _fetch_first_image(conn, row.get("images") or [])
    entry.thumb_url = entry.image_url
    db.session.add(entry)
    return True


def _mirror_post(conn: PeerConnection, row: dict) -> bool:
    remote_id = row.get("id") or row.get("slug")
    if remote_id is None or _existing("post", remote_id):
        return False
    entry = MirrorEntry(
        kind="post",
        remote_id=str(remote_id),
        title=(row.get("title") or "")[:160],
        summary=(row.get("summary") or "")[:300],
        author=row.get("author") or "",
        remote_url=row.get("url") or "",
        payload_json=json.dumps(row, ensure_ascii=False),
        published_at=_parse_dt(row.get("published_at") or row.get("created_at")),
    )
    db.session.add(entry)
    return True


def _mirror_vow(conn: PeerConnection, row: dict) -> bool:
    """对方那边签下的约定，镜像过来只作展示。

    本机不再提供签名入口 —— 一份约定只能在一台机器上签，签名才有意义。
    """
    remote_id = row.get("id")
    if remote_id is None or _existing("vow", remote_id):
        return False
    entry = MirrorEntry(
        kind="vow",
        remote_id=str(remote_id),
        title=(row.get("title") or "")[:160],
        summary=(row.get("content") or "")[:300],
        payload_json=json.dumps(row, ensure_ascii=False),
        published_at=_parse_dt(row.get("created_at")),
    )
    db.session.add(entry)
    return True


def _mirror_anniversary(conn: PeerConnection, row: dict) -> bool:
    remote_id = row.get("id")
    if remote_id is None or _existing("anniversary", remote_id):
        return False
    entry = MirrorEntry(
        kind="anniversary",
        remote_id=str(remote_id),
        title=(row.get("title") or "")[:120],
        summary=row.get("note") or "",
        payload_json=json.dumps(row, ensure_ascii=False),
        published_at=_parse_dt(row.get("anchor_on")),
    )
    db.session.add(entry)
    return True


def _parse_dt(raw):
    if not raw:
        return None
    from datetime import datetime

    text = str(raw).replace("Z", "").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:26], fmt)
        except ValueError:
            continue
    return None


# --------------------------------------------------------------------------
# 图片代理：对方站的图，从本机转出去
# --------------------------------------------------------------------------
def _fetch_first_image(conn: PeerConnection, images: list) -> str:
    if not images:
        return ""
    return fetch_image(conn, images[0]) or ""


def fetch_image(conn: PeerConnection, path: str) -> str:
    """把对方站的一张图缓存到本机，返回本地 URL。

    只放行 http(s) 和以 / 开头的相对路径 —— 传 `file:///etc/passwd`
    这种进来就成任意文件读取了。
    """
    base = conn.partner_url.rstrip("/")
    if path.startswith(("http://", "https://")):
        url = path
    elif path.startswith("/"):
        url = base + path
    else:
        return ""

    cached = _cache_path(conn, url)
    if cached.exists():
        return _url_for_cache(cached.name)

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, stream=True)
        if resp.status_code != 200:
            return ""
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if not ctype.startswith("image/"):
            return ""
        data = resp.raw.read(MAX_IMAGE_BYTES + 1, decode_content=True)
        if len(data) > MAX_IMAGE_BYTES:
            return ""
    except requests.RequestException:
        return ""

    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return _url_for_cache(cached.name)


def _cache_path(conn: PeerConnection, url: str) -> Path:
    ext = Path(urlparse(url).path).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}:
        ext = ".img"
    name = hashlib.sha256(f"{conn.partner_url}|{url}".encode()).hexdigest()[:32] + ext
    return Path(current_app.config["PEER_CACHE_FOLDER"]) / name


def _url_for_cache(name: str) -> str:
    from flask import url_for

    return url_for("couple.peer_image", name=name)


# --------------------------------------------------------------------------
# 给模板/页面用
# --------------------------------------------------------------------------
def mirror_moments(limit: int = 12) -> list:
    rows = (
        MirrorEntry.query.filter_by(kind="moment")
        .order_by(MirrorEntry.published_at.desc().nullslast(), MirrorEntry.id.desc())
        .limit(limit)
        .all()
    )
    return [r.as_dict() for r in rows]


def mirror_posts(limit: int = 6) -> list:
    rows = (
        MirrorEntry.query.filter_by(kind="post")
        .order_by(MirrorEntry.published_at.desc().nullslast(), MirrorEntry.id.desc())
        .limit(limit)
        .all()
    )
    return [r.as_dict() for r in rows]


def mirror_vows() -> list:
    return [r.as_dict() for r in MirrorEntry.query.filter_by(kind="vow").order_by(MirrorEntry.id).all()]


def mirror_anniversaries() -> list:
    return [
        r.as_dict()
        for r in MirrorEntry.query.filter_by(kind="anniversary").order_by(MirrorEntry.id).all()
    ]


def summary() -> dict:
    conn = connection()
    counts = {
        kind: MirrorEntry.query.filter_by(kind=kind).count()
        for kind in ("moment", "post", "vow", "anniversary")
    }
    return {
        "conn": conn,
        "connected": is_connected(conn),
        "counts": counts,
        "total": sum(counts.values()),
        "my_token": _local_peer_token(),
    }


# --------------------------------------------------------------------------
# 本机对外提供的内容（对方来拉）
# --------------------------------------------------------------------------
def _guard_token(provided: str) -> bool:
    expected = _local_peer_token()
    if not provided:
        return True  # 没配令牌就只认能访问到本机的机器
    return provided == expected


def outgoing_moments(limit: int = 20) -> list:
    couple = Couple.query.first()
    if couple is None:
        return []
    ids = [i for i in (couple.user_a_id, couple.user_b_id) if i]
    rows = (
        Moment.query.filter(Moment.author_id.in_(ids), Moment.is_public.is_(True))
        .order_by(Moment.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": m.id,
            "content": m.content,
            "images": m.image_list,
            "location": m.location,
            "mood": m.mood,
            "author": m.author_line,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]


def outgoing_posts(limit: int = 20) -> list:
    from flask import url_for

    rows = (
        Post.query.filter_by(status="published")
        .order_by(Post.published_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "summary": p.summary or p.plain_excerpt,
            "author": p.author.display_name if p.author else "",
            "published_at": p.published_at.isoformat() if p.published_at else "",
            "url": url_for("blog.post_detail", slug=p.slug, _external=False),
        }
        for p in rows
    ]


def outgoing_vows() -> list:
    couple = Couple.query.first()
    if couple is None:
        return []
    rows = Vow.query.filter_by(couple_id=couple.id).all()
    return [
        {
            "id": v.id,
            "title": v.title,
            "content": v.content,
            "effective": v.is_effective,
            "progress": v.progress,
            "created_at": v.created_at.isoformat(),
        }
        for v in rows
    ]


# --------------------------------------------------------------------------
# 演示互连：本机造一个「对方站点」，不用真联网也能看到效果
# --------------------------------------------------------------------------
DEMO_PEER_URL = "https://demo-partner.loveyouforever.local"


def seed_demo_peer() -> dict:
    """造一份演示用的互连数据。

    这不是「模拟同步」，而是直接往镜像表里写带标记的内容 —— 演示站不该
    为了看效果去联网。真互连走 `connect()` + `sync()`。
    """
    conn = connection()
    if conn is None:
        conn = PeerConnection(
            partner_url=DEMO_PEER_URL,
            partner_name="小可爱 & 站长",
            partner_names="小可爱、站长",
            partner_site="永远爱你（她的那台）",
            partner_sealed=True,
            enabled=True,
            status="ok",
            last_seen_at=utcnow(),
            last_sync_at=utcnow(),
        )
        db.session.add(conn)
        db.session.commit()

    stats = {"moment": 0, "post": 0, "vow": 0, "anniversary": 0}
    demo_rows = [
        ("moment", "1", "今天她那边下雨了，说想我了。", "小可爱", {"images": []}),
        ("moment", "2", "路过花店，买了她喜欢的那种。", "站长", {"images": []}),
        ("moment", "3", "她在收拾房间，说要把我的位置留出来。", "小可爱", {"images": []}),
        ("post", "1", "写给两百天后的我们", "小可爱", {}),
        ("post", "2", "关于吵架这件事的一点心得", "站长", {}),
        ("vow", "1", "每年一起看一次海", "小可爱", {"effective": True}),
        ("vow", "2", "吵架不过夜", "站长", {"effective": False}),
        ("anniversary", "1", "她的生日", "小可爱", {"anchor_on": "1998-03-14"}),
        ("anniversary", "2", "第一次见面", "站长", {"anchor_on": "2021-05-20"}),
    ]
    for i, (kind, remote_id, title, author, extra) in enumerate(demo_rows):
        key = f"demo-{kind}-{remote_id}"
        if _existing(kind, key):
            continue
        payload = {"id": remote_id, "title": title, "author": author, **extra}
        db.session.add(
            MirrorEntry(
                kind=kind,
                remote_id=key,
                title=title[:200],
                summary=title[:200],
                author=author,
                payload_json=json.dumps(payload, ensure_ascii=False),
                published_at=utcnow() - timedelta(hours=i * 7),
            )
        )
        stats[kind] += 1
    db.session.commit()
    return stats


def clear_demo_peer() -> int:
    """清掉演示互连造出来的东西（真互连的内容不动）。"""
    rows = MirrorEntry.query.filter(MirrorEntry.remote_id.like("demo-%")).all()
    for r in rows:
        db.session.delete(r)
    conn = connection()
    if conn is not None and conn.partner_url == DEMO_PEER_URL:
        db.session.delete(conn)
    db.session.commit()
    return len(rows)


def outgoing_anniversaries() -> list:
    from app.services import anniversary_service

    couple = Couple.query.first()
    if couple is None:
        return []
    return [
        {
            "id": a.id,
            "title": a.title,
            "anchor_on": a.anchor_on.isoformat() if a.anchor_on else "",
            "note": a.note,
            "kind": a.kind,
            "days_left": a.days_left(),
        }
        for a in anniversary_service.list_all(couple)
    ]

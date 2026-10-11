"""情侣绑定、「永远爱你」、约定、时间线，以及双站互连的对外接口。"""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import BindToken, Couple, CoupleEvent, User, Vow, WISH_MOODS
from app.models.mixins import utcnow
from app.services import couple_service, peer_service, site_service
from app.services.couple_service import CoupleError

couple_bp = Blueprint("couple", __name__, url_prefix="/couple")


@couple_bp.route("/")
@login_required
def home():
    couple = current_user.couple
    if couple is None:
        return redirect(url_for("couple.bind"))
    vows = Vow.query.filter_by(couple_id=couple.id).order_by(Vow.created_at.desc()).all()
    events = CoupleEvent.query.filter_by(couple_id=couple.id).order_by(
        CoupleEvent.happened_on.desc().nullslast(), CoupleEvent.id.desc()
    ).all()
    stats = couple_service.couple_stats(couple)
    tampered = couple_service.detect_tamper(couple)

    from app.services import anniversary_service

    anniversaries = anniversary_service.list_all(couple)

    from app.services import wish_service

    peer = peer_service.summary()
    return render_template(
        "couple/home.html",
        couple=couple,
        vows=vows,
        events=events,
        stats=stats,
        tampered=tampered,
        anniversaries=anniversaries,
        anniversary_humanize=anniversary_service.humanize,
        wishes=wish_service.recent(10),
        wish_moods=WISH_MOODS,
        peer=peer,
        peer_conn=peer["conn"],
        peer_timeline=peer_service.mirror_moments(6),
        peer_anniversaries=peer_service.mirror_anniversaries(),
        peer_vows=peer_service.mirror_vows(),
    )


@couple_bp.route("/anniversaries/add", methods=["POST"])
@login_required
def anniversary_add():
    """在情侣页直接加一个日子，不用绕去后台。"""
    couple = current_user.couple
    if couple is None:
        return redirect(url_for("couple.bind"))

    from datetime import date

    from app.services import anniversary_service

    title = (request.form.get("title") or "").strip()
    raw = (request.form.get("anchor_on") or "").strip()
    try:
        anchor = date.fromisoformat(raw) if raw else None
    except ValueError:
        anchor = None

    if not title or anchor is None:
        flash("名字和日期都要填哦", "error")
    else:
        anniversary_service.create(
            couple,
            title,
            anchor,
            kind=request.form.get("kind") or "anniversary",
            repeat_yearly=bool(request.form.get("repeat_yearly")),
            icon=request.form.get("icon") or "",
            is_pinned=bool(request.form.get("is_pinned")),
        )
        flash(f"「{title}」记下了", "success")
    return redirect(url_for("couple.home") + "#anniversaries")


@couple_bp.route("/wish", methods=["POST"])
@login_required
def wish_post():
    """在首页顶上贴一句话。"""
    from app.services import wish_service

    content = (request.form.get("content") or "").strip()
    if not content:
        flash("总得写点什么吧", "error")
    else:
        wish_service.post(current_user, content, request.form.get("mood") or "sweet")
        flash("贴好了，门口那句话换了。", "success")
    return redirect(request.form.get("next") or url_for("blog.index"))


@couple_bp.route("/wish/<int:wish_id>/delete", methods=["POST"])
@login_required
def wish_delete(wish_id: int):
    from app.services import wish_service

    if not current_user.is_admin:
        abort(403)
    wish_service.delete(wish_id)
    flash("删掉了", "info")
    return redirect(request.form.get("next") or url_for("blog.index"))


@couple_bp.route("/bind")
@login_required
def bind():
    if current_user.is_bound:
        return redirect(url_for("couple.home"))
    tokens = []
    if current_user.can_bind():
        tokens = (
            BindToken.query.filter_by(issuer_id=current_user.id, used=False)
            .order_by(BindToken.created_at.desc())
            .all()
        )
    return render_template("couple/bind.html", tokens=tokens)


@couple_bp.route("/bind/create", methods=["POST"])
@login_required
def create_token():
    try:
        token = couple_service.create_bind_token(current_user, hours=int(request.form.get("hours", 72)))
        flash("握手码已生成，把它交给 TA 吧。", "success")
        return redirect(url_for("couple.bind", token=token.token))
    except CoupleError as exc:
        flash(str(exc), "error")
        return redirect(url_for("couple.bind"))


@couple_bp.route("/bind/accept", methods=["POST"])
@login_required
def accept_token():
    raw = (request.form.get("token") or "").strip()
    partner_site = (request.form.get("partner_site") or "").strip()
    try:
        couple_service.accept_bind_token(current_user, raw, partner_site)
        flash("绑定成功！从这一刻起，我们写进同一段时光。", "success")
        return redirect(url_for("couple.home"))
    except CoupleError as exc:
        flash(str(exc), "error")
        return redirect(url_for("couple.bind"))


@couple_bp.route("/seal", methods=["POST"])
@login_required
def seal():
    couple = current_user.couple
    if couple is None:
        abort(404)
    confirm = (request.form.get("confirm") or "").strip()
    if confirm != "我确定":
        flash('请输入「我确定」三个字才能永封。', "error")
        return redirect(url_for("couple.home"))
    try:
        couple_service.seal_couple(couple, current_user)
        flash("已永封。从此数据库里，只有我们两个人。", "success")
    except CoupleError as exc:
        flash(str(exc), "error")
    return redirect(url_for("couple.home"))


@couple_bp.route("/vow/new", methods=["POST"])
@login_required
def new_vow():
    couple = current_user.couple
    if couple is None:
        abort(404)
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    kind = request.form.get("kind") or "promise"
    require_both = bool(request.form.get("require_both", True))
    if not title:
        flash("约定得有个名字", "error")
        return redirect(url_for("couple.home"))
    couple_service.create_vow(couple, title, content, kind, require_both)
    flash("约定已写下，等两个人签名。", "success")
    return redirect(url_for("couple.home"))


@couple_bp.route("/vow/<int:vow_id>/sign", methods=["POST"])
@login_required
def sign_vow(vow_id: int):
    vow = db.session.get(Vow, vow_id) or abort(404)
    try:
        couple_service.sign_vow(vow, current_user)
        flash("已签名。这句话，我认。", "success")
    except CoupleError as exc:
        flash(str(exc), "error")
    return redirect(url_for("couple.home"))


@couple_bp.route("/event/new", methods=["POST"])
@login_required
def new_event():
    couple = current_user.couple
    if couple is None:
        abort(404)
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("给这个日子起个名字吧", "error")
        return redirect(url_for("couple.home"))
    happened = request.form.get("happened_on") or ""
    from datetime import date

    parsed = None
    if happened:
        try:
            parsed = date.fromisoformat(happened)
        except ValueError:
            parsed = None
    ev = CoupleEvent(
        couple_id=couple.id,
        title=title,
        detail=request.form.get("detail") or "",
        happened_on=parsed or utcnow().date(),
        kind=request.form.get("kind") or "daily",
        location=request.form.get("location") or "",
    )
    db.session.add(ev)
    db.session.commit()
    flash("时间线又多了一天。", "success")
    return redirect(url_for("couple.home"))


@couple_bp.route("/settings", methods=["POST"])
@login_required
def update_settings():
    couple = current_user.couple
    if couple is None:
        abort(404)
    couple.name = (request.form.get("name") or couple.name).strip()
    couple.slogan = (request.form.get("slogan") or couple.slogan).strip()
    couple.note = request.form.get("note") or couple.note
    anniversary_raw = request.form.get("anniversary") or ""
    if anniversary_raw:
        from datetime import date

        try:
            couple.anniversary = date.fromisoformat(anniversary_raw)
        except ValueError:
            pass
    db.session.commit()
    flash("已保存", "success")
    return redirect(url_for("couple.home"))


@couple_bp.route("/merged")
@login_required
def merged():
    """情侣所有文章内容合并视图。"""
    couple = current_user.couple
    if couple is None:
        return redirect(url_for("couple.bind"))
    q = couple_service.merged_posts(couple)
    from app.utils.helpers import paginate

    page = paginate(q, 12)
    return render_template("couple/merged.html", couple=couple, posts=page.items, pagination=page)


# --------------------------------------------------------------------------
# 开放 API：给「双方站点互连」用
# --------------------------------------------------------------------------
@couple_bp.route("/api/handshake", methods=["POST"])
def api_handshake():
    """对方站点调用这里验证握手码。

    请求体：{"token": "...", "site": "https://...", "fingerprint": "..."}
    """
    data = request.get_json(silent=True) or {}
    token_raw = (data.get("token") or "").strip()
    if not token_raw:
        return jsonify({"ok": False, "message": "缺少 token"}), 400

    from app.models import BindToken

    token = BindToken.query.filter_by(token=token_raw).first()
    if token is None:
        return jsonify({"ok": False, "message": "握手码不存在"}), 404
    if not token.alive:
        return jsonify({"ok": False, "message": "握手码已失效"}), 410

    issuer = db.session.get(User, token.issuer_id)
    return jsonify(
        {
            "ok": True,
            "issuer": issuer.username if issuer else "",
            "issuer_nickname": issuer.display_name if issuer else "",
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        }
    )


@couple_bp.route("/api/wish")
def api_wish():
    """首页顶上那句话，供对方站点展示。

    只给公开的：隐藏的寄语不该从接口漏出去。
    """
    from app.services import wish_service

    wish = wish_service.current()
    if wish is None or not wish.is_public:
        return jsonify({"ok": True, "has_wish": False})
    return jsonify(
        {
            "ok": True,
            "has_wish": True,
            "content": wish.content,
            "mood": wish.mood,
            "mood_label": wish.mood_label,
            "author": wish.author.display_name if wish.author else "",
            "created_at": wish.created_at.isoformat(),
            "is_today": wish_service.is_today(wish),
        }
    )


@couple_bp.route("/api/info")
def api_info():
    """对外暴露本站的情侣信息，供对方站点展示互通。"""
    couple = Couple.query.first()
    if couple is None:
        return jsonify({"ok": True, "bound": False})
    return jsonify(
        {
            "ok": True,
            "bound": True,
            "sealed": couple.sealed,
            "name": couple.name,
            "slogan": couple.slogan,
            "days_together": couple.days_together,
            "members": [
                {"nickname": m.display_name, "role": m.role_text, "avatar": m.avatar}
                for m in couple.members
            ],
            "site": site_service.get("site_name", ""),
        }
    )


# --------------------------------------------------------------------------
# 双站互连：本机对外提供的内容接口
#
# 只给「关系两边都确认过」的内容：瞬间只出公开的，文章只出已发布的。
# 私密的东西（隐藏的瞬间/草稿/小纸条）一条都不出。
# --------------------------------------------------------------------------
def _peer_token_ok() -> bool:
    provided = (request.headers.get("X-LYF-Peer") or request.args.get("token") or "").strip()
    return peer_service._guard_token(provided)


def _peer_guard():
    if not _peer_token_ok():
        abort(403)


@couple_bp.route("/peer/moments")
def peer_moments():
    """对方来拉本站的瞬间。"""
    _peer_guard()
    limit = min(request.args.get("limit", 20, type=int), 50)
    return jsonify({"ok": True, "rows": peer_service.outgoing_moments(limit)})


@couple_bp.route("/peer/posts")
def peer_posts():
    _peer_guard()
    limit = min(request.args.get("limit", 20, type=int), 50)
    return jsonify({"ok": True, "rows": peer_service.outgoing_posts(limit)})


@couple_bp.route("/peer/vows")
def peer_vows():
    _peer_guard()
    return jsonify({"ok": True, "rows": peer_service.outgoing_vows()})


@couple_bp.route("/peer/anniversaries")
def peer_anniversaries():
    _peer_guard()
    return jsonify({"ok": True, "rows": peer_service.outgoing_anniversaries()})


@couple_bp.route("/images/<name>")
def peer_image(name: str):
    """对方站的图片，从本机转出去。

    name 只允许是 32 位十六进制 + 扩展名 —— 直接拿用户传的路径去读文件
    就是经典的目录穿越，这里卡死在文件名白名单上。
    """
    import re
    from pathlib import Path

    from flask import current_app, send_from_directory

    if not re.fullmatch(r"[0-9a-f]{32}\.[A-Za-z0-9]{1,5}", name):
        abort(404)
    folder = Path(current_app.config["PEER_CACHE_FOLDER"])
    if not (folder / name).exists():
        abort(404)
    resp = send_from_directory(folder, name, max_age=86400)
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp

"""站点体检。

`flask doctor` 已经有了，但它只在命令行里能跑 —— 真正会出问题的人
不一定会 ssh 上去敲命令。这里把同一套判断搬到后台，让人打开后台
就能看见「哪里不对劲」。

每项检查返回：
    {"level": "ok|warn|error", "title": ..., "detail": ..., "fix": ...}
fix 是「怎么修」的一句话，不写的话用户只知道坏了，不知道怎么办。
"""
from datetime import timedelta
from pathlib import Path

from flask import current_app

from app.models import BackupRecord, Couple, Post, SiteSetting, User
from app.models.mixins import utcnow


def _item(level: str, title: str, detail: str = "", fix: str = "") -> dict:
    return {"level": level, "title": title, "detail": detail, "fix": fix}


# --------------------------------------------------------------------------
# 各项检查
# --------------------------------------------------------------------------
def check_secret_key() -> dict:
    key = current_app.config.get("SECRET_KEY") or ""
    if len(key) < 32:
        return _item(
            "error",
            "SECRET_KEY 太短",
            f"当前长度 {len(key)}，session 与情侣指纹都依赖它。",
            "在 instance/secret_key 或环境变量 LYF_SECRET_KEY 里换一个足够长的随机串。",
        )
    return _item("ok", "SECRET_KEY 正常", f"长度 {len(key)}")


def check_default_password() -> dict:
    """默认密码还在不在。这是最要紧的一条。"""
    admin = User.query.filter_by(username="admin").first()
    if admin is None:
        return _item("ok", "没有名为 admin 的账号")
    if admin.check_password("loveyou"):
        return _item(
            "error",
            "默认密码还没改",
            "admin / loveyou 是全站通行的钥匙，任何访客都能试。",
            "在「用户」里给自己改密码，或删掉 admin 用新账号。",
        )
    return _item("ok", "默认密码已修改")


def check_site_url() -> dict:
    url = (SiteSetting.get("site_url") or "").strip()
    if not url:
        return _item(
            "warn",
            "站点地址没填",
            "绑定校验、RSS、sitemap、分享卡片都靠它。现在会自动猜，猜错就全错。",
            "在「站点设置 → 基本信息」里填上完整地址，比如 https://love.example.com",
        )
    if not url.startswith(("http://", "https://")):
        return _item("warn", "站点地址格式可疑", url, "要带上 http:// 或 https://")
    return _item("ok", "站点地址已配置", url)


def check_admin_count() -> dict:
    n = User.query.filter_by(is_admin=True).count()
    if n == 0:
        return _item(
            "error",
            "没有管理员账号",
            "没人能进后台。",
            "flask create-admin 新建一个管理员。",
        )
    if n > 1:
        return _item("warn", f"有 {n} 个管理员", "人越多，默认密码这种问题越难收拾。", "确认这些都是你自己。")
    return _item("ok", "管理员账号正常", "1 个")


def check_writable_dirs() -> dict:
    bad = []
    for label, path in (("上传目录", current_app.config["UPLOAD_FOLDER"]),
                        ("备份目录", current_app.config["BACKUP_FOLDER"])):
        p = Path(path)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            bad.append(label)
            continue
        if not p.exists() or not p.is_dir():
            bad.append(label)
    if bad:
        return _item(
            "error",
            f"{'、'.join(bad)}不可写",
            "传图、备份都会失败。",
            "检查目录权限（chown/chmod），或改 LYF_ 配置指向别处。",
        )
    return _item("ok", "目录可写")


def check_backup_freshness(days: int = 7) -> dict:
    latest = BackupRecord.query.order_by(BackupRecord.created_at.desc()).first()
    if latest is None:
        return _item(
            "warn",
            "一次备份都没有",
            "数据库里是你们全部的文字和照片。",
            "在「备份」里点一次「创建快照」，再挂个定时任务。",
        )
    age = utcnow() - latest.created_at
    if age > timedelta(days=days):
        return _item(
            "warn",
            f"最近一次备份是 {age.days} 天前",
            latest.filename,
            "建议每天自动备份一次（见「备份」页里的 crontab 示例）。",
        )
    return _item("ok", "备份是最新的", f"{latest.filename} · {latest.size_human}")


def check_backup_disk() -> dict:
    from app.services import backup_service

    usage = backup_service.disk_usage()
    free = usage.get("free_bytes") or 0
    if free < 200 * 1024 * 1024:
        return _item(
            "error",
            "磁盘快满了",
            f"剩余 {usage.get('free_human')}，备份可能写不下去。",
            "清一下旧备份或扩容。",
        )
    return _item("ok", "磁盘空间充足", f"剩余 {usage.get('free_human')}")


def check_couple_state() -> dict:
    from app.services import couple_service

    couple = Couple.query.first()
    if couple is None:
        return _item("ok", "还没有绑定情侣关系", "一个人写也挺好。")
    if couple_service.detect_tamper(couple):
        return _item(
            "error",
            "情侣关系数据被外部改动过",
            "永封指纹对不上。",
            "检查是否有人直接改过数据库。",
        )
    if not couple.is_complete:
        return _item(
            "warn",
            "关系只有一半",
            "等另一半拿握手码来绑定。",
            "在「情侣关系」里生成握手码，或让对方发起绑定。",
        )
    state = "已永封" if couple.sealed else "已绑定（未永封）"
    return _item("ok", f"情侣关系正常 · {state}", f"已相爱 {couple.days_together} 天")


def check_content() -> dict:
    published = Post.query.filter_by(status="published").count()
    drafts = Post.query.filter_by(status="draft").count()
    if published == 0:
        return _item("warn", "还没有发布的文章", f"草稿 {drafts} 篇", "后台写一篇，或者导入旧数据。")
    return _item("ok", "内容正常", f"已发布 {published} 篇，草稿 {drafts} 篇")


CHECKS = (
    check_default_password,
    check_secret_key,
    check_admin_count,
    check_site_url,
    check_writable_dirs,
    check_couple_state,
    check_backup_freshness,
    check_backup_disk,
    check_content,
)


def run_all() -> dict:
    items = []
    for fn in CHECKS:
        try:
            items.append(fn())
        except Exception as exc:  # 体检脚本自己不能把后台搞崩
            current_app.logger.warning("体检项 %s 出错: %s", fn.__name__, exc)
            items.append(_item("warn", f"{fn.__name__} 检查失败", str(exc)[:120]))

    errors = sum(1 for i in items if i["level"] == "error")
    warns = sum(1 for i in items if i["level"] == "warn")
    if errors:
        headline = f"{errors} 项需要立刻处理"
    elif warns:
        headline = f"{warns} 项值得看一眼"
    else:
        headline = "一切正常"
    # 键名用 rows 而不是 items：Jinja 里 report.items 是 dict 的方法
    return {
        "rows": items,
        "errors": errors,
        "warnings": warns,
        "ok": len(items) - errors - warns,
        "headline": headline,
        "level": "error" if errors else ("warn" if warns else "ok"),
        "checked_at": utcnow(),
    }


def badge() -> dict:
    """给仪表盘用的一行摘要。"""
    result = run_all()
    return {"level": result["level"], "headline": result["headline"],
            "errors": result["errors"], "warnings": result["warnings"]}

"""零碎小工具：slug、时间格式化、IP、分页等。"""
import hashlib
import re
import unicodedata
from datetime import date, datetime, timezone
from functools import wraps

from flask import abort, current_app, flash, redirect, request, url_for
from flask_login import current_user


def slugify(text: str, fallback: str = "item") -> str:
    """生成 URL slug。

    中文标题用 pinyin 依赖太重，改成「保留汉字 + 去掉空格符号」，
    URL 里出现中文在现代浏览器里完全没问题，且可读性更好。
    """
    if not text:
        return fallback
    text = unicodedata.normalize("NFKC", str(text)).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^\w\u4e00-\u9fff\-]", "", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or fallback


def unique_slug(model, base: str, field: str = "slug", exclude_id=None) -> str:
    slug = slugify(base)
    candidate = slug
    n = 2
    while True:
        q = model.query.filter(getattr(model, field) == candidate)
        if exclude_id:
            q = q.filter(model.id != exclude_id)
        if q.first() is None:
            return candidate
        candidate = f"{slug}-{n}"
        n += 1


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def humanize_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    delta = (now() - dt).total_seconds()
    if delta < 60:
        return "刚刚"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前"
    if delta < 86400 * 30:
        return f"{int(delta // 86400)} 天前"
    return dt.strftime("%Y-%m-%d")


def fmt_date(dt, pattern: str = "%Y-%m-%d") -> str:
    if not dt:
        return ""
    if isinstance(dt, (date, datetime)):
        return dt.strftime(pattern)
    return str(dt)


def client_ip() -> str:
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def ip_key() -> str:
    return hashlib.sha256((client_ip() + (current_app.config["SECRET_KEY"] or "")).encode()).hexdigest()[:32]


def allowed_image(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.full_path))
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return wrapper


def couple_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.full_path))
        if not current_user.is_bound:
            flash("这个页面需要先完成情侣绑定哦", "warning")
            return redirect(url_for("couple.bind"))
        return f(*args, **kwargs)

    return wrapper


def paginate(query, per_page: int = 10):
    page = request.args.get("page", 1, type=int)
    return query.paginate(page=page, per_page=per_page, error_out=False)


def truncate(text: str, length: int = 80) -> str:
    if not text:
        return ""
    return text if len(text) <= length else text[: length - 1] + "…"


def page_url(page: int) -> str:
    """给当前请求生成带上指定页码的 URL。

    模板里没法用 ** 解包，所以把这件事挪到 Python 里做。
    """
    args = request.args.to_dict(flat=True)
    args["page"] = page
    return url_for(request.endpoint, **(request.view_args or {}), **args)

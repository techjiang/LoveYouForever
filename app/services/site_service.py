"""站点信息聚合：导航、页脚、SEO、主题。"""
from functools import lru_cache

from flask import current_app, request, url_for
from flask_login import current_user

from app import APP_AUTHOR, APP_AUTHOR_URL, APP_NAME, APP_REPO_URL
from app.models import Category, Couple, CustomPage, Page, SiteSetting
from app.services import theme_service

DEFAULT_SETTINGS = {
    "site_name": "永远爱你",
    "site_subtitle": "写给我们两个人的博客",
    "site_description": "一个只属于我们俩的小站，记录每天的心动。",
    "site_keywords": "情侣博客,永远爱你,LoveYouForever,恋爱记录",
    "site_url": "",
    "site_logo": "",
    "site_favicon": "",
    "icp": "",
    "footer_text": "",
    "theme_key": "sakura",
    "theme_mode": "light",
    "theme_overrides": "{}",
    "hero_title": "和你在一起的每一天，都值得被记下来",
    "hero_subtitle": "这里没有别人的故事，只有我们",
    "hero_image": "",
    "couple_name": "我们",
    "couple_slogan": "一生一世，永不分离",
    "hero_show_days": "1",
    "posts_per_page": "10",
    "comment_enabled": "1",
    "guest_comment": "1",
    "about_md": "",
    "seo_og_image": "",
    "auto_backup": "1",
    "backup_interval_hours": "24",
}


def ensure_defaults() -> None:
    for key, value in DEFAULT_SETTINGS.items():
        SiteSetting.set(key, value)


def site_context() -> dict:
    settings = SiteSetting.as_dict()
    couple = Couple.query.first()
    cfg = {
        "name": settings.get("site_name", DEFAULT_SETTINGS["site_name"]),
        "subtitle": settings.get("site_subtitle", ""),
        "description": settings.get("site_description", ""),
        "keywords": settings.get("site_keywords", ""),
        "url": settings.get("site_url", ""),
        "logo": settings.get("site_logo", ""),
        "favicon": settings.get("site_favicon", ""),
        "icp": settings.get("icp", ""),
        "footer_text": settings.get("footer_text", ""),
        "hero_title": settings.get("hero_title", ""),
        "hero_subtitle": settings.get("hero_subtitle", ""),
        "hero_image": settings.get("hero_image", ""),
        "theme_key": settings.get("theme_key", "sakura"),
        "theme_mode": settings.get("theme_mode", "light"),
        "couple_slogan": settings.get("couple_slogan", ""),
        "couple": couple,
        "couple_name": couple.name if couple else settings.get("couple_name", "我们"),
        "days_together": couple.days_together if couple else 0,
        "nav_pages": nav_pages(),
        "categories": Category.query.order_by(Category.sort_order, Category.id).all(),
        "powered_by": POWERED_BY_TEXT,
        "author": {"name": APP_AUTHOR, "url": APP_AUTHOR_URL},
        "repo": APP_REPO_URL,
        "app_name": APP_NAME,
    }
    return cfg


POWERED_BY_TEXT = f"Powered by {APP_AUTHOR} & {APP_NAME}"


def nav_pages() -> list:
    """导航栏里的页面。内建页 + 自定义页 + 插件贡献的入口。"""
    items = []
    for p in Page.query.filter_by(show_in_nav=True).order_by(Page.sort_order, Page.id).all():
        items.append({"title": p.title, "url": url_for("misc.page", key=p.key), "key": p.key, "kind": "page"})
    for p in (
        CustomPage.query.filter_by(show_in_nav=True, status="published")
        .order_by(CustomPage.sort_order, CustomPage.id)
        .all()
    ):
        items.append({"title": p.title, "url": url_for("misc.custom_page", slug=p.slug), "key": p.slug, "kind": "custom"})
    try:
        from app.plugins.manager import manager

        items.extend(manager.collect_nav_items())
    except Exception:
        pass
    return items


def theme_css() -> str:
    settings = SiteSetting.as_dict()
    key = settings.get("theme_key", "sakura")
    overrides = {}
    raw = settings.get("theme_overrides", "{}")
    if raw:
        import json

        try:
            overrides = json.loads(raw)
        except json.JSONDecodeError:
            overrides = {}
    colors = theme_service.resolve_colors(key, overrides)
    theme = theme_service.get_theme(key)
    mode = settings.get("theme_mode") or theme.get("mode", "light")
    css = theme_service.css_variables(colors)
    return f"{css}\n[data-theme=\"{mode}\"] {{ color-scheme: {mode}; }}"


def seo_meta(title: str = "", description: str = "", image: str = "") -> dict:
    settings = SiteSetting.as_dict()
    base = settings.get("site_url") or (request.host_url.rstrip("/") if request else "")
    return {
        "title": f"{title} · {settings.get('site_name', '永远爱你')}" if title else settings.get("site_name", "永远爱你"),
        "description": description or settings.get("site_description", ""),
        "keywords": settings.get("site_keywords", ""),
        "image": image or settings.get("seo_og_image", ""),
        "url": request.url if request else base,
    }


def save_settings(pairs: dict) -> None:
    for key, value in pairs.items():
        SiteSetting.set(key, value)


def get(key: str, default=None):
    value = SiteSetting.get(key)
    if value is None or value == "":
        return DEFAULT_SETTINGS.get(key, default)
    return value


def get_bool(key: str, default: bool = False) -> bool:
    value = get(key, "1" if default else "0")
    return str(value).lower() in {"1", "true", "yes", "on"}

"""首次初始化：默认设置、默认页面、默认账号、示例内容。

只做「缺什么补什么」，绝不覆盖用户已有数据。
"""
from flask import current_app

from app.extensions import db
from app.models import Category, Couple, CustomPage, Page, SiteSetting, User
from app.services import site_service


def init_site(app=None) -> None:
    site_service.ensure_defaults()
    _ensure_pages()
    _ensure_admin()
    _ensure_categories()


def _ensure_pages() -> None:
    defaults = [
        ("about", "关于我们", 1, True,
         "## 关于我们\n\n这里是我们的地方。\n\n::love[你是我所有故事的开始]\n\n"
         "在后台「页面管理」里可以随时改写这段文字。\n"),
        ("links", "友链", 2, True,
         "## 友情链接\n\n想和我们做邻居？在评论区留下你的站点吧。\n"),
        ("message", "留言板", 3, True,
         "## 留言板\n\n有什么想说的，写在这里就好。\n"),
    ]
    for key, title, order, show_nav, md in defaults:
        if Page.query.filter_by(key=key).first() is None:
            from app.utils.markdown_render import render

            db.session.add(
                Page(
                    key=key,
                    title=title,
                    content_md=md,
                    content_html=render(md),
                    is_system=True,
                    show_in_nav=show_nav,
                    sort_order=order,
                )
            )
    db.session.commit()


def _ensure_admin() -> None:
    if User.query.count() > 0:
        return
    from app.utils.helpers import slugify  # noqa: F401

    admin = User(
        username="admin",
        nickname="站长",
        email="admin@example.com",
        is_admin=True,
        role_label="",
    )
    admin.set_password("loveyou")
    db.session.add(admin)
    db.session.commit()
    current_app.logger.warning(
        "已创建默认账号 admin / loveyou，请登录后立刻修改密码！"
    )


def _ensure_categories() -> None:
    defaults = [
        ("日常", "记录平凡日子里的小确幸", "🌤️", "#ff8fb1"),
        ("旅行", "一起去过的地方", "🧳", "#3d7dff"),
        ("美食", "和你吃过的每一顿饭", "🍜", "#f0a63c"),
        ("纪念日", "值得标记的日子", "🎂", "#8b6cf0"),
    ]
    if Category.query.count() > 0:
        return
    for i, (name, desc, icon, color) in enumerate(defaults):
        db.session.add(
            Category(
                name=name,
                slug=site_service_slug(name),
                description=desc,
                icon=icon,
                color=color,
                sort_order=i,
            )
        )
    db.session.commit()


def site_service_slug(name: str) -> str:
    from app.utils.helpers import slugify

    return slugify(name, fallback="category")

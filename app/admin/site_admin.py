"""后台站点设置：基本信息、首页、SEO、评论、友链。"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import FriendLink, SiteSetting
from app.services import site_service
from app.utils.helpers import admin_required

#: 分组 -> [(key, label, type, hint)]
SETTING_GROUPS = {
    "basic": {
        "title": "基本信息",
        "icon": "⚙️",
        "fields": [
            ("site_name", "站点名称", "text", "会出现在浏览器标签和页头"),
            ("site_subtitle", "副标题", "text", ""),
            ("site_description", "站点描述", "textarea", "用于 SEO 与分享卡片"),
            ("site_keywords", "关键词", "text", "英文逗号分隔"),
            ("site_url", "站点地址", "text", "例如 https://love.example.com，用于 RSS 与绑定校验"),
            ("site_logo", "Logo 图片地址", "image", ""),
            ("site_favicon", "Favicon 地址", "image", ""),
            ("icp", "备案信息", "text", ""),
            ("footer_text", "页脚自定义文字", "textarea", "会显示在锁定署名上方"),
        ],
    },
    "home": {
        "title": "首页展示",
        "icon": "🏠",
        "fields": [
            ("hero_title", "首屏大标题", "text", ""),
            ("hero_subtitle", "首屏副标题", "text", ""),
            ("hero_image", "首屏背景图", "image", ""),
            ("hero_show_days", "显示相爱天数", "bool", ""),
            ("posts_per_page", "每页文章数", "number", ""),
        ],
    },
    "couple": {
        "title": "情侣设置",
        "icon": "💞",
        "fields": [
            ("couple_name", "关系名称", "text", "还没绑定时显示"),
            ("couple_slogan", "关系宣言", "text", ""),
        ],
    },
    "comment": {
        "title": "互动与评论",
        "icon": "💬",
        "fields": [
            ("comment_enabled", "开启评论", "bool", ""),
            ("guest_comment", "允许游客评论", "bool", "关闭后必须登录才能评论"),
            ("open_register", "开放注册", "bool", "情侣站通常两人用，建议注册完就关"),
        ],
    },
    "seo": {
        "title": "SEO 与分享",
        "icon": "🔍",
        "fields": [
            ("seo_og_image", "默认分享图", "image", "微信/Twitter 分享时的封面"),
        ],
    },
    "backup": {
        "title": "备份策略",
        "icon": "🛡️",
        "fields": [
            ("auto_backup", "开启自动备份", "bool", ""),
            ("backup_interval_hours", "自动备份间隔（小时）", "number", "配合服务器上的定时任务使用"),
        ],
    },
}


@admin_bp.route("/site", methods=["GET", "POST"])
@login_required
@admin_required
def site():
    if request.method == "POST":
        group = request.form.get("_group", "basic")
        fields = SETTING_GROUPS.get(group, {}).get("fields", [])
        for key, _label, ftype, _hint in fields:
            if ftype == "bool":
                SiteSetting.set(key, "1" if request.form.get(key) else "0", group)
            else:
                SiteSetting.set(key, (request.form.get(key) or "").strip(), group)
        db.session.commit()
        flash("设置已保存", "success")
        return redirect(url_for("admin.site", tab=group))
    return render_template(
        "admin/site.html",
        groups=SETTING_GROUPS,
        settings=SiteSetting.as_dict(),
        active_tab=request.args.get("tab", "basic"),
    )


@admin_bp.route("/friends", methods=["GET", "POST"])
@login_required
@admin_required
def friends():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        url = (request.form.get("url") or "").strip()
        if name and url:
            db.session.add(
                FriendLink(
                    name=name,
                    url=url,
                    avatar=(request.form.get("avatar") or "").strip(),
                    description=(request.form.get("description") or "").strip(),
                    email=(request.form.get("email") or "").strip(),
                    is_couple_site=bool(request.form.get("is_couple_site")),
                    is_approved=True,
                )
            )
            db.session.commit()
            flash("友链已添加", "success")
        return redirect(url_for("admin.friends"))
    links = FriendLink.query.order_by(FriendLink.is_approved, FriendLink.sort_order, FriendLink.id).all()
    return render_template("admin/friends.html", links=links)


@admin_bp.route("/friends/<int:link_id>/approve", methods=["POST"])
@login_required
@admin_required
def friend_approve(link_id: int):
    link = db.session.get(FriendLink, link_id)
    link.is_approved = not link.is_approved
    db.session.commit()
    flash("状态已切换", "success")
    return redirect(url_for("admin.friends"))


@admin_bp.route("/friends/<int:link_id>/edit", methods=["POST"])
@login_required
@admin_required
def friend_edit(link_id: int):
    link = db.session.get(FriendLink, link_id)
    link.name = (request.form.get("name") or link.name).strip()
    link.url = (request.form.get("url") or link.url).strip()
    link.avatar = (request.form.get("avatar") or "").strip()
    link.description = (request.form.get("description") or "").strip()
    link.is_couple_site = bool(request.form.get("is_couple_site"))
    db.session.commit()
    flash("友链已更新", "success")
    return redirect(url_for("admin.friends"))


@admin_bp.route("/friends/<int:link_id>/delete", methods=["POST"])
@login_required
@admin_required
def friend_delete(link_id: int):
    link = db.session.get(FriendLink, link_id)
    db.session.delete(link)
    db.session.commit()
    flash("已删除", "info")
    return redirect(url_for("admin.friends"))

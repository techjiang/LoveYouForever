"""后台主题与配色管理。"""
import json

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import SiteSetting
from app.services import site_service, theme_service
from app.utils.helpers import admin_required


@admin_bp.route("/theme", methods=["GET", "POST"])
@login_required
@admin_required
def theme():
    if request.method == "POST":
        action = request.form.get("_action", "apply")
        if action == "apply":
            key = request.form.get("theme_key") or "sakura"
            mode = request.form.get("theme_mode") or "light"
            overrides = {
                k.replace("color_", ""): request.form.get(k)
                for k in request.form
                if k.startswith("color_") and request.form.get(k)
            }
            SiteSetting.set("theme_key", key, "theme")
            SiteSetting.set("theme_mode", mode, "theme")
            SiteSetting.set("theme_overrides", json.dumps(overrides, ensure_ascii=False), "theme")
            db.session.commit()
            flash("主题已应用", "success")
        elif action == "save_custom":
            name = (request.form.get("custom_name") or "").strip()
            if not name:
                flash("给主题起个名字吧", "error")
            else:
                overrides = {
                    k.replace("color_", ""): request.form.get(k)
                    for k in request.form
                    if k.startswith("color_") and request.form.get(k)
                }
                theme_service.save_theme(
                    name,
                    {
                        "title": name,
                        "description": (request.form.get("custom_desc") or "我自己的配色").strip(),
                        "mode": request.form.get("theme_mode") or "light",
                        "colors": theme_service.resolve_colors(request.form.get("theme_key", "sakura"), overrides),
                    },
                )
                flash(f"主题「{name}」已保存到 themes/ 目录", "success")
        elif action == "delete":
            name = request.form.get("theme_key") or ""
            if theme_service.delete_theme(name):
                flash("主题已删除", "info")
            else:
                flash("内置主题不能删除", "warning")
        return redirect(url_for("admin.theme"))

    settings = SiteSetting.as_dict()
    current_key = settings.get("theme_key", "sakura")
    overrides = {}
    try:
        overrides = json.loads(settings.get("theme_overrides") or "{}")
    except json.JSONDecodeError:
        overrides = {}
    return render_template(
        "admin/theme.html",
        themes=theme_service.all_themes(),
        tokens=theme_service.COLOR_TOKENS,
        current_key=current_key,
        current_mode=settings.get("theme_mode", "light"),
        overrides=overrides,
        resolved=theme_service.resolve_colors(current_key, overrides),
    )


@admin_bp.route("/theme/preview")
@login_required
@admin_required
def theme_preview():
    """返回指定主题的 CSS 变量，前端即时预览用。"""
    key = request.args.get("key", "sakura")
    overrides = {}
    raw = request.args.get("overrides")
    if raw:
        try:
            overrides = json.loads(raw)
        except json.JSONDecodeError:
            overrides = {}
    colors = theme_service.resolve_colors(key, overrides)
    return jsonify({"css": theme_service.css_variables(colors), "colors": colors})

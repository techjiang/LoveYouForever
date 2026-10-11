"""后台插件管理。"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import PluginRecord
from app.plugins.manager import manager
from app.utils.helpers import admin_required


@admin_bp.route("/plugins")
@login_required
@admin_required
def plugins():
    found = manager.discover()
    records = {r.name: r for r in PluginRecord.query.all()}
    items = []
    for name, plugin in found.items():
        rec = records.get(name)
        items.append(
            {
                "meta": plugin.to_dict(),
                "record": rec,
                "enabled": bool(rec and rec.enabled),
                "config": _config_dict(rec),
            }
        )
    # 已停用但从目录里删掉的残留记录
    orphans = [r for r in records.values() if r.name not in found]
    return render_template("admin/plugins.html", items=items, orphans=orphans)


def _config_dict(rec) -> dict:
    import json

    if rec is None:
        return {}
    try:
        return json.loads(rec.config_json or "{}")
    except json.JSONDecodeError:
        return {}


@admin_bp.route("/plugins/<name>/toggle", methods=["POST"])
@login_required
@admin_required
def plugin_toggle(name: str):
    rec = PluginRecord.query.filter_by(name=name).first()
    if rec and rec.enabled:
        manager.disable(name)
        flash(f"插件 {name} 已停用，重启后完全生效", "info")
    else:
        if manager.enable(name):
            flash(f"插件 {name} 已启用，重启后完全生效", "success")
        else:
            flash("插件不存在", "error")
    return redirect(url_for("admin.plugins"))


@admin_bp.route("/plugins/<name>/config", methods=["POST"])
@login_required
@admin_required
def plugin_config(name: str):
    found = manager.discover()
    plugin = found.get(name)
    if plugin is None:
        flash("插件不存在", "error")
        return redirect(url_for("admin.plugins"))
    config = {}
    for key, _label, ftype, _default in plugin.settings:
        if ftype == "bool":
            config[key] = bool(request.form.get(f"cfg_{key}"))
        else:
            config[key] = request.form.get(f"cfg_{key}", "")
    manager.save_config(name, config)
    flash("插件配置已保存", "success")
    return redirect(url_for("admin.plugins"))


@admin_bp.route("/plugins/<name>/cleanup", methods=["POST"])
@login_required
@admin_required
def plugin_cleanup(name: str):
    rec = PluginRecord.query.filter_by(name=name).first()
    if rec:
        db.session.delete(rec)
        db.session.commit()
        flash("插件残留记录已清理", "info")
    return redirect(url_for("admin.plugins"))

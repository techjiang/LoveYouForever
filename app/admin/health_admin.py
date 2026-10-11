"""后台「站点体检」。

把 flask doctor 的判断搬进后台，外加一页能直接看的报告。
"""
from flask import flash, redirect, render_template, url_for
from flask_login import login_required

from app.admin import admin_bp
from app.services import health_service
from app.utils.helpers import admin_required


@admin_bp.route("/health")
@login_required
@admin_required
def health():
    return render_template("admin/health.html", report=health_service.run_all())


@admin_bp.route("/health/recheck", methods=["POST"])
@login_required
@admin_required
def health_recheck():
    report = health_service.run_all()
    flash(f"体检完成：{report['headline']}", "info" if report["level"] == "ok" else "warning")
    return redirect(url_for("admin.health"))

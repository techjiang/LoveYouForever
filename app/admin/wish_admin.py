"""后台「门口寄语」管理。

前台首页只显示一条，后台要看得到全部 —— 包括哪些删掉了、
谁贴得比较勤。这只是个顺手的小面板，不打算做成内容管理。
"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import DailyWish, User, WISH_MOODS
from app.services import wish_service
from app.utils.helpers import admin_required


@admin_bp.route("/wishes")
@login_required
@admin_required
def wishes():
    items = DailyWish.query.order_by(DailyWish.created_at.desc()).limit(100).all()
    showing = wish_service.current()
    return render_template(
        "admin/wishes.html",
        wishes=items,
        moods=WISH_MOODS,
        current_id=showing.id if showing else None,
        users=User.query.order_by(User.id).all(),
    )


@admin_bp.route("/wishes/new", methods=["POST"])
@login_required
@admin_required
def wish_new():
    content = (request.form.get("content") or "").strip()
    if not content:
        flash("内容不能为空", "error")
    else:
        author_id = request.form.get("author_id", type=int) or current_user.id
        author = db.session.get(User, author_id) or current_user
        wish_service.post(author, content, request.form.get("mood") or "sweet")
        flash("已贴上", "success")
    return redirect(url_for("admin.wishes"))


@admin_bp.route("/wishes/<int:wish_id>/toggle", methods=["POST"])
@login_required
@admin_required
def wish_toggle(wish_id: int):
    wish = db.session.get(DailyWish, wish_id)
    if wish is None:
        flash("找不到这条", "error")
    else:
        wish.is_public = not wish.is_public
        db.session.commit()
        flash("已设为公开" if wish.is_public else "已隐藏（只有登录的人能看到）", "info")
    return redirect(url_for("admin.wishes"))


@admin_bp.route("/wishes/<int:wish_id>/delete", methods=["POST"])
@login_required
@admin_required
def wish_delete(wish_id: int):
    wish_service.delete(wish_id)
    flash("已删除", "info")
    return redirect(url_for("admin.wishes"))

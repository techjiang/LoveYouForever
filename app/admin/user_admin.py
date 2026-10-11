"""后台用户管理。"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import Note, User
from app.utils.helpers import admin_required


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or len(password) < 6:
            flash("用户名不能为空，密码至少 6 位", "error")
        elif User.query.filter_by(username=username).first():
            flash("用户名已存在", "error")
        else:
            u = User(
                username=username,
                nickname=(request.form.get("nickname") or username).strip(),
                email=(request.form.get("email") or "").strip() or None,
                role_label=(request.form.get("role_label") or "").strip(),
                is_admin=bool(request.form.get("is_admin")),
            )
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash("用户已创建", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/users.html", users=User.query.order_by(User.id).all())


@admin_bp.route("/users/<int:user_id>/edit", methods=["POST"])
@login_required
@admin_required
def user_edit(user_id: int):
    u = db.session.get(User, user_id)
    u.nickname = (request.form.get("nickname") or u.nickname).strip()
    u.email = (request.form.get("email") or "").strip() or None
    u.role_label = (request.form.get("role_label") or "").strip()
    u.pet_title = (request.form.get("pet_title") or "").strip()
    u.bio = (request.form.get("bio") or "").strip()
    u.is_admin = bool(request.form.get("is_admin"))
    u.is_active_account = bool(request.form.get("is_active", True))
    new_pwd = request.form.get("new_password") or ""
    if new_pwd:
        if len(new_pwd) < 6:
            flash("新密码至少 6 位", "error")
            return redirect(url_for("admin.users"))
        u.set_password(new_pwd)
    db.session.commit()
    flash("用户已更新", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def user_delete(user_id: int):
    u = db.session.get(User, user_id)
    if u.id == current_user.id:
        flash("不能删除自己", "error")
    elif u.sealed or u.couple_id:
        flash("这个账号已经绑定/永封在情侣关系里，不能删除", "error")
    else:
        db.session.delete(u)
        db.session.commit()
        flash("用户已删除", "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/notes")
@login_required
@admin_required
def notes():
    items = Note.query.order_by(Note.created_at.desc()).limit(200).all()
    return render_template("admin/notes.html", notes=items)

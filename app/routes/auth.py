"""登录、注册、退出、个人资料。"""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import SiteSetting, User
from app.services import site_service
from app.utils.helpers import client_ip, slugify

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("blog.index"))

    if request.method == "POST":
        account = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter(
            (User.username == account) | (User.email == account)
        ).first()

        if user is None or not user.check_password(password):
            flash("账号或密码不对，再想想？", "error")
        elif not user.is_active_account:
            flash("这个账号已被停用。", "error")
        else:
            login_user(user, remember=remember)
            user.touch_login(client_ip())
            db.session.commit()
            flash(f"欢迎回来，{user.display_name}", "success")
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("blog.index"))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("blog.index"))

    # 站点是否开放注册，默认开（情侣站一般就两个人，注册完可以关掉）
    open_reg = site_service.get_bool("open_register", True)
    if not open_reg:
        flash("本站暂不开放注册，请联系站长。", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        nickname = (request.form.get("nickname") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        role_label = (request.form.get("role_label") or "").strip()

        errors = []
        if len(username) < 3:
            errors.append("用户名至少 3 个字符")
        if not re.fullmatch(r"[\w\u4e00-\u9fff.\-]+", username):
            errors.append("用户名只能包含字母、数字、下划线、点、短横线或汉字")
        if len(password) < 6:
            errors.append("密码至少 6 位")
        if password != confirm:
            errors.append("两次输入的密码不一致")
        if User.query.filter_by(username=username).first():
            errors.append("这个用户名已经有人用了")
        if email and User.query.filter_by(email=email).first():
            errors.append("这个邮箱已经注册过了")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            user = User(
                username=username,
                nickname=nickname or username,
                email=email or None,
                role_label=role_label,
                # 第一个注册的人自动成为管理员
                is_admin=User.query.count() == 0,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("注册成功，去登录吧～", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("已退出登录", "info")
    return redirect(url_for("blog.index"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.nickname = (request.form.get("nickname") or "").strip() or current_user.username
        current_user.bio = (request.form.get("bio") or "").strip()
        current_user.email = (request.form.get("email") or "").strip() or None
        current_user.role_label = (request.form.get("role_label") or "").strip()
        current_user.pet_title = (request.form.get("pet_title") or "").strip()
        db.session.commit()
        flash("资料已更新", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html")


@auth_bp.route("/password", methods=["POST"])
@login_required
def change_password():
    old = request.form.get("old_password") or ""
    new = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    if not current_user.check_password(old):
        flash("原密码不对", "error")
    elif len(new) < 6:
        flash("新密码至少 6 位", "error")
    elif new != confirm:
        flash("两次输入的新密码不一致", "error")
    else:
        current_user.set_password(new)
        db.session.commit()
        flash("密码已修改，请记牢哦", "success")
    return redirect(url_for("auth.profile"))

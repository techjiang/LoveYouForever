"""后台情侣管理：关系总览、约定、时间线、内容合并。

注意：这里刻意「没有」解绑功能。产品规则如此，后台也不开后门。
"""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import BindToken, Couple, CoupleEvent, User, Vow
from app.services import couple_service
from app.utils.helpers import admin_required, paginate


@admin_bp.route("/couple")
@login_required
@admin_required
def couple():
    c = Couple.query.first()
    tokens = BindToken.query.order_by(BindToken.created_at.desc()).limit(10).all()
    return render_template(
        "admin/couple.html",
        couple=c,
        tokens=tokens,
        tampered=couple_service.detect_tamper(c) if c else False,
        stats=couple_service.couple_stats(c) if c else {},
        users=User.query.order_by(User.id).all(),
    )


@admin_bp.route("/couple/vows")
@login_required
@admin_required
def vows():
    c = Couple.query.first()
    if c is None:
        flash("还没有绑定情侣关系", "warning")
        return redirect(url_for("admin.couple"))
    items = Vow.query.filter_by(couple_id=c.id).order_by(Vow.created_at.desc()).all()
    return render_template("admin/vows.html", couple=c, vows=items)


@admin_bp.route("/couple/vows/new", methods=["POST"])
@login_required
@admin_required
def vow_new():
    c = Couple.query.first()
    if c is None:
        flash("还没有绑定情侣关系", "warning")
        return redirect(url_for("admin.couple"))
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("约定标题不能为空", "error")
    else:
        couple_service.create_vow(
            c,
            title,
            request.form.get("content") or "",
            request.form.get("kind") or "promise",
            bool(request.form.get("require_both", True)),
        )
        flash("约定已创建", "success")
    return redirect(url_for("admin.vows"))


@admin_bp.route("/couple/vows/<int:vow_id>/delete", methods=["POST"])
@login_required
@admin_required
def vow_delete(vow_id: int):
    vow = db.session.get(Vow, vow_id)
    if vow is None:
        flash("这条约定已经不存在了", "error")
        return redirect(url_for("admin.vows"))
    db.session.delete(vow)
    db.session.commit()
    flash("约定已删除", "info")
    return redirect(url_for("admin.vows"))


@admin_bp.route("/couple/events")
@login_required
@admin_required
def events():
    c = Couple.query.first()
    if c is None:
        return redirect(url_for("admin.couple"))
    items = CoupleEvent.query.filter_by(couple_id=c.id).order_by(CoupleEvent.happened_on.desc()).all()
    return render_template("admin/events.html", couple=c, events=items)


@admin_bp.route("/couple/events/new", methods=["POST"])
@login_required
@admin_required
def event_new():
    from datetime import date

    c = Couple.query.first()
    if c is None:
        return redirect(url_for("admin.couple"))
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("事件名不能为空", "error")
        return redirect(url_for("admin.events"))
    raw = request.form.get("happened_on") or ""
    try:
        parsed = date.fromisoformat(raw) if raw else None
    except ValueError:
        parsed = None
    db.session.add(
        CoupleEvent(
            couple_id=c.id,
            title=title,
            detail=request.form.get("detail") or "",
            kind=request.form.get("kind") or "daily",
            happened_on=parsed,
            location=request.form.get("location") or "",
        )
    )
    db.session.commit()
    flash("事件已添加", "success")
    return redirect(url_for("admin.events"))


@admin_bp.route("/couple/events/<int:event_id>/delete", methods=["POST"])
@login_required
@admin_required
def event_delete(event_id: int):
    ev = db.session.get(CoupleEvent, event_id)
    if ev is None:
        flash("这条记录已经不存在了", "error")
        return redirect(url_for("admin.events"))
    db.session.delete(ev)
    db.session.commit()
    flash("已删除", "info")
    return redirect(url_for("admin.events"))


@admin_bp.route("/couple/merged")
@login_required
@admin_required
def merged():
    """双方内容合并总览。"""
    c = Couple.query.first()
    if c is None:
        return redirect(url_for("admin.couple"))
    page = paginate(couple_service.merged_posts(c), 20)
    return render_template("admin/merged.html", couple=c, posts=page.items, pagination=page)


@admin_bp.route("/couple/seal", methods=["POST"])
@login_required
@admin_required
def seal():
    c = Couple.query.first()
    if c is None:
        abort(404)
    confirm = (request.form.get("confirm") or "").strip()
    if confirm != "我确定":
        flash('请输入「我确定」才能永封。', "error")
        return redirect(url_for("admin.couple"))
    try:
        couple_service.seal_couple(c, current_user if current_user.id in (c.user_a_id, c.user_b_id) else c.members[0])
        flash("关系已永封，从此不可解除。", "success")
    except Exception as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.couple"))


@admin_bp.route("/couple/token", methods=["POST"])
@login_required
@admin_required
def create_token():
    """以某个用户身份生成握手码，方便站长帮忙牵线。"""
    user_id = request.form.get("user_id", type=int)
    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        flash("请选择要发起绑定的账号", "error")
        return redirect(url_for("admin.couple"))
    try:
        token = couple_service.create_bind_token(user)
        flash(f"握手码已生成：{token.token}", "success")
    except Exception as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.couple"))

"""后台瞬间管理。"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import Moment, MomentComment
from app.utils.helpers import admin_required, paginate


@admin_bp.route("/moments")
@login_required
@admin_required
def moments():
    page = paginate(Moment.query.order_by(Moment.created_at.desc()), 20)
    return render_template("admin/moments.html", moments=page.items, pagination=page)


@admin_bp.route("/moments/new", methods=["POST"])
@login_required
@admin_required
def moment_new():
    content = (request.form.get("content") or "").strip()
    urls = request.form.getlist("images")
    if not content and not urls:
        flash("内容不能为空", "error")
    else:
        db.session.add(
            Moment(
                content=content,
                images="\n".join(u for u in urls if u.strip()),
                location=(request.form.get("location") or "").strip(),
                mood=(request.form.get("mood") or "").strip(),
                author_id=current_user.id,
                co_authored=bool(request.form.get("co_authored")),
                co_author_id=current_user.partner.id if (request.form.get("co_authored") and current_user.partner) else None,
                is_public=bool(request.form.get("is_public", True)),
            )
        )
        db.session.commit()
        flash("瞬间已发布", "success")
    return redirect(url_for("admin.moments"))


@admin_bp.route("/moments/<int:moment_id>/edit", methods=["POST"])
@login_required
@admin_required
def moment_edit(moment_id: int):
    m = db.session.get(Moment, moment_id)
    m.content = request.form.get("content") or ""
    m.is_public = bool(request.form.get("is_public"))
    m.is_pinned = bool(request.form.get("is_pinned"))
    db.session.commit()
    flash("已更新", "success")
    return redirect(url_for("admin.moments"))


@admin_bp.route("/moments/<int:moment_id>/delete", methods=["POST"])
@login_required
@admin_required
def moment_delete(moment_id: int):
    m = db.session.get(Moment, moment_id)
    db.session.delete(m)
    db.session.commit()
    flash("瞬间已删除", "info")
    return redirect(url_for("admin.moments"))


@admin_bp.route("/comments")
@login_required
@admin_required
def comments():
    page = paginate(MomentComment.query.order_by(MomentComment.created_at.desc()), 25)
    return render_template("admin/comments.html", comments=page.items, pagination=page)


@admin_bp.route("/comments/<int:comment_id>/delete", methods=["POST"])
@login_required
@admin_required
def comment_delete(comment_id: int):
    c = db.session.get(MomentComment, comment_id)
    moment_id = c.moment_id
    db.session.delete(c)
    moment = db.session.get(Moment, moment_id)
    if moment:
        moment.comment_count = max((moment.comment_count or 1) - 1, 0)
    db.session.commit()
    return redirect(request.referrer or url_for("admin.comments"))

"""瞬间：两个人的共同朋友圈。"""
from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import Moment, MomentComment, MomentLike, User
from app.utils.helpers import ip_key, paginate

moment_bp = Blueprint("moment", __name__, url_prefix="/moments")


def _visible_query():
    q = Moment.query.filter_by(is_public=True)
    if current_user.is_authenticated:
        q = Moment.query
    return q


@moment_bp.route("/")
def index():
    page = paginate(_visible_query().order_by(Moment.is_pinned.desc(), Moment.created_at.desc()), 8)
    liked_ids = set()
    if current_user.is_authenticated:
        liked_ids = {
            l.moment_id
            for l in MomentLike.query.filter_by(user_id=current_user.id).all()
        }
    else:
        liked_ids = {
            l.moment_id for l in MomentLike.query.filter_by(guest_key=ip_key()).all()
        }
    return render_template("moment/index.html", moments=page.items, pagination=page, liked_ids=liked_ids)


@moment_bp.route("/new", methods=["GET", "POST"])
def new():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.full_path))
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        images = request.form.getlist("images")
        if not content and not images:
            from flask import flash

            flash("总得写点什么吧", "error")
            return redirect(url_for("moment.new"))
        m = Moment(
            content=content,
            images="\n".join(images),
            location=request.form.get("location") or "",
            mood=request.form.get("mood") or "",
            author_id=current_user.id,
            co_authored=bool(request.form.get("co_authored")),
            co_author_id=current_user.partner.id if (request.form.get("co_authored") and current_user.partner) else None,
            is_public=bool(request.form.get("is_public", True)),
        )
        db.session.add(m)
        db.session.commit()
        return redirect(url_for("moment.index"))
    return render_template("moment/new.html")


@moment_bp.route("/<int:moment_id>/like", methods=["POST"])
def like(moment_id: int):
    m = db.session.get(Moment, moment_id) or abort(404)
    if current_user.is_authenticated:
        existing = MomentLike.query.filter_by(moment_id=m.id, user_id=current_user.id).first()
        if existing:
            db.session.delete(existing)
            m.like_count = max((m.like_count or 1) - 1, 0)
            liked = False
        else:
            db.session.add(MomentLike(moment_id=m.id, user_id=current_user.id, guest_key=""))
            m.like_count = (m.like_count or 0) + 1
            liked = True
    else:
        key = ip_key()
        existing = MomentLike.query.filter_by(moment_id=m.id, guest_key=key).first()
        if existing:
            db.session.delete(existing)
            m.like_count = max((m.like_count or 1) - 1, 0)
            liked = False
        else:
            db.session.add(MomentLike(moment_id=m.id, user_id=None, guest_key=key))
            m.like_count = (m.like_count or 0) + 1
            liked = True
    db.session.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"ok": True, "liked": liked, "count": m.like_count})
    return redirect(request.referrer or url_for("moment.index"))


@moment_bp.route("/<int:moment_id>/comment", methods=["POST"])
def comment(moment_id: int):
    m = db.session.get(Moment, moment_id) or abort(404)
    content = (request.form.get("content") or "").strip()
    if not content:
        return redirect(request.referrer or url_for("moment.index"))

    if not current_user.is_authenticated and not _guest_comment_allowed():
        from flask import flash

        flash("请先登录再评论", "warning")
        return redirect(url_for("auth.login", next=request.full_path))

    reply_to_id = request.form.get("reply_to_id", type=int)
    c = MomentComment(
        moment_id=m.id,
        author_id=current_user.id if current_user.is_authenticated else None,
        guest_name=(request.form.get("guest_name") or "").strip() if not current_user.is_authenticated else "",
        guest_site=(request.form.get("guest_site") or "").strip() if not current_user.is_authenticated else "",
        content=content,
        reply_to_id=reply_to_id,
    )
    db.session.add(c)
    m.comment_count = (m.comment_count or 0) + 1
    db.session.commit()
    return redirect(url_for("moment.index") + f"#m{m.id}")


def _guest_comment_allowed() -> bool:
    from app.services import site_service

    return site_service.get_bool("guest_comment", True)


@moment_bp.route("/<int:moment_id>")
def detail(moment_id: int):
    m = db.session.get(Moment, moment_id) or abort(404)
    if not m.is_public and not current_user.is_authenticated:
        abort(404)
    return render_template("moment/detail.html", moment=m)


@moment_bp.route("/timeline")
def timeline():
    """瞬间时间线：按月分组。"""
    moments = _visible_query().order_by(Moment.created_at.desc()).all()
    grouped: dict = {}
    for m in moments:
        key = m.created_at.strftime("%Y-%m")
        grouped.setdefault(key, []).append(m)
    return render_template("moment/timeline.html", grouped=grouped)

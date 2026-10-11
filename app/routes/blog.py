"""前台主站：首页、文章、分类、标签、归档、搜索。"""
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request
from sqlalchemy import func, or_

from app.extensions import db
from app.models import Category, Couple, Moment, Post, SiteSetting, Tag
from app.services import site_service
from app.utils.helpers import paginate

blog_bp = Blueprint("blog", __name__)


def _published():
    return Post.query.filter_by(status="published")


def _per_page() -> int:
    try:
        return max(int(site_service.get("posts_per_page", 10)), 1)
    except (TypeError, ValueError):
        return 10


@blog_bp.route("/")
def index():
    page = paginate(_published().order_by(Post.is_pinned.desc(), Post.published_at.desc()), _per_page())
    pinned = _published().filter_by(is_pinned=True).order_by(Post.published_at.desc()).limit(3).all()
    recent_moments = (
        Moment.query.filter_by(is_public=True)
        .order_by(Moment.created_at.desc())
        .limit(4)
        .all()
    )
    couple = Couple.query.first()
    stats = {
        "posts": _published().count(),
        "categories": Category.query.count(),
        "moments": Moment.query.filter_by(is_public=True).count(),
        "days": couple.days_together if couple else 0,
    }

    return render_template(
        "index.html",
        posts=page.items,
        pagination=page,
        pinned=pinned,
        moments=recent_moments,
        stats=stats,
        couple=couple,
    )


@blog_bp.route("/posts")
def post_list():
    q = _published()
    keyword = (request.args.get("q") or "").strip()
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(Post.title.ilike(like), Post.content_md.ilike(like), Post.summary.ilike(like)))
    page = paginate(q.order_by(Post.is_pinned.desc(), Post.published_at.desc()), _per_page())
    return render_template("post_list.html", posts=page.items, pagination=page, keyword=keyword)


@blog_bp.route("/post/<slug>")
def post_detail(slug: str):
    post = _published().filter_by(slug=slug).first()
    if post is None:
        # 草稿作者本人可以预览
        from flask_login import current_user

        draft = Post.query.filter_by(slug=slug).first()
        if draft and current_user.is_authenticated and (
            current_user.id in (draft.author_id, draft.co_author_id) or current_user.is_admin
        ):
            post = draft
        else:
            abort(404)

    post.bump_view()
    db.session.commit()

    html = post.content_html
    try:
        from app.plugins.manager import manager

        html = manager.dispatch_post_render(post, html)
    except Exception:
        pass

    prev_post = (
        _published()
        .filter(Post.published_at < post.published_at, Post.id != post.id)
        .order_by(Post.published_at.desc())
        .first()
    )
    next_post = (
        _published()
        .filter(Post.published_at > post.published_at, Post.id != post.id)
        .order_by(Post.published_at.asc())
        .first()
    )
    related = _related_posts(post)

    return render_template(
        "post_detail.html",
        post=post,
        post_html=html,
        prev_post=prev_post,
        next_post=next_post,
        related=related,
    )


def _related_posts(post: Post, limit: int = 4):
    """内容互联：先按手动指定，再按标签重合度，最后按同分类兜底。"""
    manual_ids = []
    if post.related_ids:
        manual_ids = [int(x) for x in post.related_ids.split(",") if x.strip().isdigit()]
    out = []
    if manual_ids:
        out = Post.query.filter(Post.id.in_(manual_ids), Post.status == "published").all()

    if len(out) < limit:
        tag_ids = [t.id for t in post.tags]
        if tag_ids:
            extra = (
                Post.query.filter(
                    Post.status == "published",
                    Post.id != post.id,
                    ~Post.id.in_([p.id for p in out] or [0]),
                    Post.tags.any(Tag.id.in_(tag_ids)),
                )
                .order_by(Post.published_at.desc())
                .limit(limit - len(out))
                .all()
            )
            out.extend(extra)

    if len(out) < limit and post.category_id:
        extra = (
            Post.query.filter(
                Post.status == "published",
                Post.id != post.id,
                Post.category_id == post.category_id,
                ~Post.id.in_([p.id for p in out] or [0]),
            )
            .order_by(Post.published_at.desc())
            .limit(limit - len(out))
            .all()
        )
        out.extend(extra)
    return out[:limit]


@blog_bp.route("/category/<slug>")
def category(slug: str):
    cat = Category.query.filter_by(slug=slug).first_or_404()
    page = paginate(
        _published().filter_by(category_id=cat.id).order_by(Post.published_at.desc()), _per_page()
    )
    return render_template("category.html", category=cat, posts=page.items, pagination=page)


@blog_bp.route("/categories")
def category_list():
    cats = Category.query.order_by(Category.sort_order, Category.id).all()
    return render_template("category_list.html", categories=cats)


@blog_bp.route("/tag/<slug>")
def tag(slug: str):
    t = Tag.query.filter_by(slug=slug).first_or_404()
    page = paginate(
        _published().filter(Post.tags.any(Tag.id == t.id)).order_by(Post.published_at.desc()), _per_page()
    )
    return render_template("tag.html", tag=t, posts=page.items, pagination=page)


@blog_bp.route("/tags")
def tag_list():
    tags = Tag.query.all()
    tags.sort(key=lambda t: t.post_count, reverse=True)
    return render_template("tag_list.html", tags=tags)


@blog_bp.route("/archive")
def archive():
    """归档：按年 -> 月分组，并给出年份统计。"""
    posts = _published().order_by(Post.published_at.desc()).all()
    tree: dict = {}
    year_counts: dict = {}
    for p in posts:
        dt = p.published_at or p.created_at
        if not dt:
            continue
        y, m = dt.year, dt.month
        tree.setdefault(y, {}).setdefault(m, []).append(p)
        year_counts[y] = year_counts.get(y, 0) + 1
    years = sorted(tree.keys(), reverse=True)
    return render_template("archive.html", tree=tree, years=years, year_counts=year_counts, total=len(posts))


@blog_bp.route("/search")
def search():
    keyword = (request.args.get("q") or "").strip()
    posts = []
    if keyword:
        like = f"%{keyword}%"
        posts = (
            _published()
            .filter(or_(Post.title.ilike(like), Post.content_md.ilike(like), Post.summary.ilike(like)))
            .order_by(Post.published_at.desc())
            .limit(50)
            .all()
        )
    return render_template("search.html", keyword=keyword, posts=posts)


@blog_bp.route("/api/stats")
def api_stats():
    couple = Couple.query.first()
    return jsonify(
        {
            "posts": _published().count(),
            "categories": Category.query.count(),
            "tags": Tag.query.count(),
            "days_together": couple.days_together if couple else 0,
        }
    )


@blog_bp.route("/love")
def love_letter():
    """彩蛋页：一封信。"""
    couple = Couple.query.first()
    return render_template("love.html", couple=couple)

"""后台内容管理：文章、分类、标签、页面、自定义页。"""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.admin import admin_bp
from app.extensions import db
from app.models import Category, CustomPage, Page, Post, Tag, User
from app.services import site_service
from app.utils.helpers import admin_required, paginate, unique_slug
from app.utils.markdown_render import extract_summary, reading_minutes, render


# ---------------------------------------------------------------- 文章
@admin_bp.route("/posts")
@login_required
@admin_required
def posts():
    q = Post.query
    status = request.args.get("status")
    if status in {"draft", "published", "private"}:
        q = q.filter_by(status=status)
    keyword = (request.args.get("q") or "").strip()
    if keyword:
        q = q.filter(Post.title.ilike(f"%{keyword}%"))
    cat_id = request.args.get("category", type=int)
    if cat_id:
        q = q.filter_by(category_id=cat_id)
    page = paginate(q.order_by(Post.created_at.desc()), 15)
    return render_template(
        "admin/posts.html",
        posts=page.items,
        pagination=page,
        categories=Category.query.order_by(Category.sort_order).all(),
        status=status,
        keyword=keyword,
        cat_id=cat_id,
    )


@admin_bp.route("/posts/new", methods=["GET", "POST"])
@login_required
@admin_required
def post_new():
    if request.method == "POST":
        post = _save_post(Post(), request.form)
        if post:
            flash("文章已保存", "success")
            return redirect(url_for("admin.posts"))
    return render_template(
        "admin/post_edit.html",
        post=None,
        categories=Category.query.order_by(Category.sort_order).all(),
        all_tags=Tag.query.order_by(Tag.name).all(),
        users=User.query.order_by(User.id).all(),
    )


@admin_bp.route("/posts/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def post_edit(post_id: int):
    post = db.session.get(Post, post_id) or _notfound()
    if request.method == "POST":
        updated = _save_post(post, request.form)
        if updated:
            flash("文章已更新", "success")
            return redirect(url_for("admin.posts"))
    return render_template(
        "admin/post_edit.html",
        post=post,
        categories=Category.query.order_by(Category.sort_order).all(),
        all_tags=Tag.query.order_by(Tag.name).all(),
        users=User.query.order_by(User.id).all(),
    )


def _save_post(post: Post, form) -> Post | None:
    title = (form.get("title") or "").strip()
    if not title:
        flash("标题不能为空", "error")
        return None

    post.title = title
    post.slug = (form.get("slug") or "").strip() or unique_slug(Post, title, exclude_id=post.id)
    if Post.query.filter(Post.slug == post.slug, Post.id != (post.id or 0)).first():
        post.slug = unique_slug(Post, post.slug, exclude_id=post.id)

    post.content_md = form.get("content_md") or ""
    post.content_html = render(post.content_md)
    post.summary = (form.get("summary") or "").strip() or extract_summary(post.content_md)
    post.cover = (form.get("cover") or "").strip()
    post.category_id = form.get("category_id", type=int) or None
    post.author_id = post.author_id or current_user.id
    post.co_author_id = form.get("co_author_id", type=int) or None
    post.co_written = bool(post.co_author_id)
    post.status = form.get("status") or "published"
    post.is_pinned = bool(form.get("is_pinned"))
    post.allow_comment = bool(form.get("allow_comment", True))
    post.related_ids = (form.get("related_ids") or "").strip()
    post.reading_minutes = reading_minutes(post.content_md)

    if not post.owner_label and post.author:
        post.owner_label = post.author.role_text

    # 标签
    tag_names = [t.strip() for t in (form.get("tags") or "").replace("，", ",").split(",") if t.strip()]
    tags = []
    for name in tag_names:
        tag = Tag.query.filter_by(name=name).first()
        if tag is None:
            tag = Tag(name=name, slug=unique_slug(Tag, name))
            db.session.add(tag)
            db.session.flush()
        tags.append(tag)
    post.tags = tags

    if post.id is None:
        db.session.add(post)
    db.session.commit()
    return post


def _notfound():
    from flask import abort

    abort(404)


@admin_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@login_required
@admin_required
def post_delete(post_id: int):
    post = db.session.get(Post, post_id) or _notfound()
    db.session.delete(post)
    db.session.commit()
    flash("文章已删除", "info")
    return redirect(url_for("admin.posts"))


@admin_bp.route("/posts/<int:post_id>/toggle", methods=["POST"])
@login_required
@admin_required
def post_toggle(post_id: int):
    post = db.session.get(Post, post_id) or _notfound()
    post.status = "draft" if post.status == "published" else "published"
    db.session.commit()
    return redirect(request.referrer or url_for("admin.posts"))


# ---------------------------------------------------------------- 分类
@admin_bp.route("/categories", methods=["GET", "POST"])
@login_required
@admin_required
def categories():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if name:
            if Category.query.filter_by(name=name).first():
                flash("分类已存在", "warning")
            else:
                db.session.add(
                    Category(
                        name=name,
                        slug=unique_slug(Category, name),
                        description=(request.form.get("description") or "").strip(),
                        icon=(request.form.get("icon") or "").strip(),
                        color=(request.form.get("color") or "").strip(),
                        sort_order=request.form.get("sort_order", type=int) or 0,
                    )
                )
                db.session.commit()
                flash("分类已添加", "success")
        return redirect(url_for("admin.categories"))
    cats = Category.query.order_by(Category.sort_order, Category.id).all()
    return render_template("admin/categories.html", categories=cats)


@admin_bp.route("/categories/<int:cat_id>/edit", methods=["POST"])
@login_required
@admin_required
def category_edit(cat_id: int):
    cat = db.session.get(Category, cat_id) or _notfound()
    cat.name = (request.form.get("name") or cat.name).strip()
    cat.description = (request.form.get("description") or "").strip()
    cat.icon = (request.form.get("icon") or "").strip()
    cat.color = (request.form.get("color") or "").strip()
    cat.sort_order = request.form.get("sort_order", type=int) or 0
    db.session.commit()
    flash("分类已更新", "success")
    return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
@admin_required
def category_delete(cat_id: int):
    cat = db.session.get(Category, cat_id) or _notfound()
    if cat.posts.count():
        flash("这个分类下还有文章，先挪走再删", "error")
    else:
        db.session.delete(cat)
        db.session.commit()
        flash("分类已删除", "info")
    return redirect(url_for("admin.categories"))


# ---------------------------------------------------------------- 标签
@admin_bp.route("/tags", methods=["GET", "POST"])
@login_required
@admin_required
def tags():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if name and not Tag.query.filter_by(name=name).first():
            db.session.add(Tag(name=name, slug=unique_slug(Tag, name), color=(request.form.get("color") or "").strip()))
            db.session.commit()
            flash("标签已添加", "success")
        return redirect(url_for("admin.tags"))
    return render_template("admin/tags.html", tags=Tag.query.order_by(Tag.name).all())


@admin_bp.route("/tags/<int:tag_id>/delete", methods=["POST"])
@login_required
@admin_required
def tag_delete(tag_id: int):
    tag = db.session.get(Tag, tag_id) or _notfound()
    db.session.delete(tag)
    db.session.commit()
    flash("标签已删除", "info")
    return redirect(url_for("admin.tags"))


# ---------------------------------------------------------------- 页面
@admin_bp.route("/pages")
@login_required
@admin_required
def pages():
    return render_template(
        "admin/pages.html",
        pages=Page.query.order_by(Page.sort_order).all(),
        custom_pages=CustomPage.query.order_by(CustomPage.sort_order).all(),
    )


@admin_bp.route("/pages/<int:page_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def page_edit(page_id: int):
    p = db.session.get(Page, page_id) or _notfound()
    if request.method == "POST":
        p.title = (request.form.get("title") or p.title).strip()
        p.content_md = request.form.get("content_md") or ""
        p.content_html = render(p.content_md)
        p.show_in_nav = bool(request.form.get("show_in_nav"))
        p.sort_order = request.form.get("sort_order", type=int) or 0
        db.session.commit()
        flash("页面已更新", "success")
        return redirect(url_for("admin.pages"))
    return render_template("admin/page_edit.html", page=p, is_custom=False)


@admin_bp.route("/custom-pages/new", methods=["POST"])
@login_required
@admin_required
def custom_page_new():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("标题不能为空", "error")
    else:
        db.session.add(
            CustomPage(
                title=title,
                slug=unique_slug(CustomPage, request.form.get("slug") or title),
                content_md="## 新页面\n\n在这里写点什么吧。\n",
                content_html=render("## 新页面\n\n在这里写点什么吧。"),
                show_in_nav=bool(request.form.get("show_in_nav")),
            )
        )
        db.session.commit()
        flash("自定义页面已创建", "success")
    return redirect(url_for("admin.pages"))


@admin_bp.route("/custom-pages/<int:pid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def custom_page_edit(pid: int):
    p = db.session.get(CustomPage, pid) or _notfound()
    if request.method == "POST":
        p.title = (request.form.get("title") or p.title).strip()
        new_slug = (request.form.get("slug") or p.slug).strip()
        if new_slug != p.slug:
            p.slug = unique_slug(CustomPage, new_slug, exclude_id=p.id)
        p.content_md = request.form.get("content_md") or ""
        p.content_html = render(p.content_md)
        p.cover = (request.form.get("cover") or "").strip()
        p.show_in_nav = bool(request.form.get("show_in_nav"))
        p.status = request.form.get("status") or "published"
        p.sort_order = request.form.get("sort_order", type=int) or 0
        db.session.commit()
        flash("页面已更新", "success")
        return redirect(url_for("admin.pages"))
    return render_template("admin/page_edit.html", page=p, is_custom=True)


@admin_bp.route("/custom-pages/<int:pid>/delete", methods=["POST"])
@login_required
@admin_required
def custom_page_delete(pid: int):
    p = db.session.get(CustomPage, pid) or _notfound()
    db.session.delete(p)
    db.session.commit()
    flash("页面已删除", "info")
    return redirect(url_for("admin.pages"))


@admin_bp.route("/preview", methods=["POST"])
@login_required
@admin_required
def preview():
    """Markdown 实时预览接口。"""
    from flask import jsonify

    text = (request.get_json(silent=True) or {}).get("content", "")
    return jsonify({"html": render(text), "minutes": reading_minutes(text)})

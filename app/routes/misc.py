"""友链、关于、留言、自定义页面、上传接口、RSS。"""
import os
import uuid
from pathlib import Path

from flask import (
    Blueprint, Response, abort, current_app, flash, jsonify, redirect,
    render_template, request, url_for,
)
from flask_login import current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import CustomPage, FriendLink, Page
from app.services import site_service
from app.utils.helpers import allowed_image
from app.utils.markdown_render import render

misc_bp = Blueprint("misc", __name__)


@misc_bp.route("/links")
def links():
    friend_links = (
        FriendLink.query.filter_by(is_approved=True)
        .order_by(FriendLink.is_couple_site.desc(), FriendLink.sort_order, FriendLink.id)
        .all()
    )
    return render_template("links.html", links=friend_links)


@misc_bp.route("/links/apply", methods=["POST"])
def apply_link():
    name = (request.form.get("name") or "").strip()
    url = (request.form.get("url") or "").strip()
    if not name or not url:
        flash("站点名和链接都得填", "error")
        return redirect(url_for("misc.links"))
    link = FriendLink(
        name=name,
        url=url,
        avatar=(request.form.get("avatar") or "").strip(),
        description=(request.form.get("description") or "").strip(),
        email=(request.form.get("email") or "").strip(),
        is_approved=False,
    )
    db.session.add(link)
    db.session.commit()
    flash("申请已提交，等站长审核～", "success")
    return redirect(url_for("misc.links"))


@misc_bp.route("/p/<key>")
def page(key: str):
    p = Page.query.filter_by(key=key).first_or_404()
    return render_template("page.html", page=p)


@misc_bp.route("/p/<key>/comment", methods=["POST"])
def page_comment(key: str):
    return redirect(url_for("misc.page", key=key))


@misc_bp.route("/<slug>")
def custom_page(slug: str):
    p = CustomPage.query.filter_by(slug=slug).first()
    if p is None or p.status != "published":
        abort(404)
    # 自定义页面支持 {{latest_posts}} 之类的简易指令
    html = _expand_directives(p.content_html or "")
    return render_template("custom_page.html", page=p, page_html=html)


DIRECTIVES = {
    "{{latest_posts}}": "blog.post_list.html_widget",
    "{{albums}}": None,
}


def _expand_directives(html: str) -> str:
    """自定义页面里的动态区块指令。

    做法很朴素：把指令替换成对应片段渲染结果，出错就原样保留。
    """
    from app.models import Album, Post

    if "{{latest_posts}}" in html:
        posts = Post.query.filter_by(status="published").order_by(Post.published_at.desc()).limit(6).all()
        fragment = render_template("partials/_latest_posts.html", posts=posts)
        html = html.replace("{{latest_posts}}", fragment)
    if "{{albums}}" in html:
        albums = Album.query.filter_by(is_public=True).order_by(Album.sort_order).limit(6).all()
        fragment = render_template("partials/_album_grid.html", albums=albums)
        html = html.replace("{{albums}}", fragment)
    return html


@misc_bp.route("/upload", methods=["POST"])
def upload():
    """统一的图片上传接口，返回 JSON。"""
    if not current_user.is_authenticated:
        return jsonify({"ok": False, "message": "请先登录"}), 401

    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"ok": False, "message": "没有选择文件"}), 400
    if not allowed_image(file.filename):
        return jsonify({"ok": False, "message": "只支持常见图片格式"}), 400

    category = request.form.get("category", "covers")
    if category not in {"covers", "photos", "moments", "avatars"}:
        category = "covers"

    ext = file.filename.rsplit(".", 1)[-1].lower()
    name = f"{uuid.uuid4().hex[:16]}.{ext}"
    dest_dir = Path(current_app.config["UPLOAD_FOLDER"]) / category
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / secure_filename(name)
    file.save(dest)

    # 尝试压缩大图
    _optimize_image(dest)

    url = url_for("static", filename=f"uploads/{category}/{name}")
    return jsonify({"ok": True, "url": url, "filename": name})


def _optimize_image(path: Path, max_width: int = 2000) -> None:
    try:
        from PIL import Image

        if path.suffix.lower() in {".svg", ".gif", ".avif"}:
            return
        with Image.open(path) as im:
            if im.width <= max_width:
                return
            ratio = max_width / im.width
            im = im.convert("RGB") if im.mode in {"RGBA", "P"} else im
            im = im.resize((max_width, int(im.height * ratio)), Image.LANCZOS)
            im.save(path, optimize=True, quality=88)
    except Exception:
        pass


@misc_bp.route("/feed.xml")
def feed():
    from app.models import Post

    posts = Post.query.filter_by(status="published").order_by(Post.published_at.desc()).limit(20).all()
    site_name = site_service.get("site_name", "永远爱你")
    site_url = site_service.get("site_url", "") or request.host_url.rstrip("/")
    items = []
    for p in posts:
        link = site_url + url_for("blog.post_detail", slug=p.slug)
        items.append(
            f"<item><title><![CDATA[{p.title}]]></title><link>{link}</link>"
            f"<guid>{link}</guid><description><![CDATA[{p.plain_excerpt}]]></description>"
            f"<pubDate>{p.published_at.strftime('%a, %d %b %Y %H:%M:%S +0800') if p.published_at else ''}</pubDate></item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{site_name}</title><link>{site_url}</link>"
        f"<description>{site_service.get('site_description', '')}</description>"
        + "".join(items)
        + "</channel></rss>"
    )
    return Response(xml, mimetype="application/rss+xml")


@misc_bp.route("/robots.txt")
def robots():
    body = "User-agent: *\nAllow: /\nSitemap: {}/sitemap.xml\n".format(
        site_service.get("site_url", "") or request.host_url.rstrip("/")
    )
    return Response(body, mimetype="text/plain")


@misc_bp.route("/sitemap.xml")
def sitemap():
    from app.models import Post

    base = site_service.get("site_url", "") or request.host_url.rstrip("/")
    urls = [base + url_for("blog.index")]
    for p in Post.query.filter_by(status="published").all():
        urls.append(base + url_for("blog.post_detail", slug=p.slug))
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    body += "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    body += "</urlset>"
    return Response(body, mimetype="application/xml")

"""LoveYouForever —— 永远爱你博客系统。

应用工厂。启动顺序：
配置 -> 扩展 -> 蓝图 -> 模板全局 -> 插件 -> CLI -> 首次初始化
"""
import os
from pathlib import Path

from flask import Flask, g, render_template, request
from flask_login import current_user

from app.config import INSTANCE_DIR, config_map
from app.extensions import csrf, db, login_manager

APP_NAME = "LoveYouForever"
APP_AUTHOR = "科技酱"
APP_AUTHOR_URL = "https://docs.asoe.cn"
APP_REPO_URL = "https://github.com/techjiang/LoveYouForever"

#: 全局底部署名 —— 这一行是项目的身份，禁止移除/修改/遮掩
POWERED_BY_HTML = (
    '<div class="lyf-powered" data-lyf-locked="true">'
    '<span>Powered by </span>'
    f'<a href="{APP_AUTHOR_URL}" target="_blank" rel="noopener">科技酱</a>'
    '<span> &amp; </span>'
    f'<a href="{APP_REPO_URL}" target="_blank" rel="noopener">LoveYouForever</a>'
    "</div>"
)


def create_app(config_name: str | None = None) -> Flask:
    config_name = config_name or os.environ.get("LYF_ENV", "development")
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_map.get(config_name, config_map["default"]))

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["BACKUP_FOLDER"]).mkdir(parents=True, exist_ok=True)

    _init_extensions(app)

    with app.app_context():
        from app import models  # noqa: F401  建表前先把模型都注册进来

        db.create_all()
        from app.services.bootstrap import init_site

        init_site(app)

    _register_blueprints(app)
    _register_jinja(app)
    _register_hooks(app)
    _register_cli(app)

    with app.app_context():
        _load_plugins(app)

    return app


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录"
    login_manager.login_message_category = "info"
    login_manager.session_protection = "strong"

    # API 接口不做 CSRF，其余表单都保护
    csrf.init_app(app)
    if app.config.get("WTF_CSRF_ENABLED", True):
        @app.before_request
        def _csrf_exempt_api():
            if request.path.startswith("/api/") and request.method == "POST":
                setattr(request, "_lyf_csrf_exempt", True)

    @app.before_request
    def _bind_session_user():
        g.current_user = current_user


def _register_blueprints(app: Flask) -> None:
    from app.admin import admin_bp
    from app.routes.auth import auth_bp
    from app.routes.blog import blog_bp
    from app.routes.couple import couple_bp
    from app.routes.gallery import gallery_bp
    from app.routes.moment import moment_bp
    from app.routes.misc import misc_bp

    app.register_blueprint(blog_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(couple_bp)
    app.register_blueprint(gallery_bp)
    app.register_blueprint(moment_bp)
    app.register_blueprint(misc_bp)
    app.register_blueprint(admin_bp)


def _register_jinja(app: Flask) -> None:
    from app.services import site_service, theme_service
    from app.utils.helpers import fmt_date, humanize_time, page_url, truncate

    @app.context_processor
    def inject_globals():
        try:
            cfg = site_service.site_context()
        except Exception:
            cfg = {}

        plugin_footer = ""
        try:
            from app.plugins.manager import manager

            plugin_footer = manager.collect_footer_html()
        except Exception:
            plugin_footer = ""

        return {
            "plugin_footer": plugin_footer,
            "site": cfg,
            "current_year": __import__("datetime").datetime.now().year,
            "powered_by_html": POWERED_BY_HTML,
            "APP_NAME": APP_NAME,
            "APP_AUTHOR": APP_AUTHOR,
            "APP_AUTHOR_URL": APP_AUTHOR_URL,
            "APP_REPO_URL": APP_REPO_URL,
            "theme_css": site_service.theme_css(),
            "nav_pages": cfg.get("nav_pages", []),
        }

    app.jinja_env.filters["humanize"] = humanize_time
    app.jinja_env.filters["fmt_date"] = fmt_date
    app.jinja_env.filters["truncate_text"] = truncate
    app.jinja_env.globals["theme_tokens"] = theme_service.COLOR_TOKENS
    app.jinja_env.globals["page_url"] = page_url


def _register_hooks(app: Flask) -> None:
    from app.utils.markdown_render import pygments_css

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.template_filter("pygments")
    def _pygments(_style=None):
        return pygments_css()

    @app.errorhandler(404)
    def _404(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def _403(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def _500(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def _load_plugins(app: Flask) -> None:
    from app.plugins.manager import manager

    try:
        manager.bootstrap(app)
    except Exception as exc:  # 插件体系坏了也要能开机
        app.logger.warning("插件系统初始化失败: %s", exc)


def _register_cli(app: Flask) -> None:
    from app.cli import register_cli

    register_cli(app)

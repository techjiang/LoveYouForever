"""后台蓝图。所有子模块都挂在这个蓝图下，统一 /admin 前缀。"""
from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/admin", template_folder="../templates/admin")

from app.admin import (  # noqa: E402,F401
    dashboard, content, gallery_admin, moment_admin, couple_admin,
    anniversary_admin, site_admin, backup_admin, plugin_admin,
    theme_admin, user_admin, wish_admin, health_admin,
    peer_admin,
)

"""后台仪表盘。"""
from datetime import timedelta

from flask import render_template
from flask_login import login_required
from sqlalchemy import func

from app.admin import admin_bp
from app.extensions import db
from app.models import (
    Album, BackupRecord, Category, Couple, FriendLink, Moment, Photo, Post,
    SiteSetting, Tag, User, Vow,
)
from app.models.mixins import utcnow
from app.services import backup_service, couple_service, health_service
from app.utils.helpers import admin_required


@admin_bp.route("/")
@login_required
@admin_required
def index():
    couple = Couple.query.first()
    stats = {
        "posts": Post.query.count(),
        "published": Post.query.filter_by(status="published").count(),
        "drafts": Post.query.filter_by(status="draft").count(),
        "categories": Category.query.count(),
        "tags": Tag.query.count(),
        "moments": Moment.query.count(),
        "albums": Album.query.count(),
        "photos": Photo.query.count(),
        "friends": FriendLink.query.count(),
        "users": User.query.count(),
        "vows": Vow.query.filter_by(couple_id=couple.id).count() if couple else 0,
        "total_views": db.session.query(func.coalesce(func.sum(Post.views), 0)).scalar() or 0,
        "days": couple.days_together if couple else 0,
    }

    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(6).all()
    recent_moments = Moment.query.order_by(Moment.created_at.desc()).limit(5).all()
    recent_backups = BackupRecord.query.order_by(BackupRecord.created_at.desc()).limit(5).all()

    # 近 14 天发布趋势
    trend = []
    today = utcnow().date()
    for i in range(13, -1, -1):
        day = today - timedelta(days=i)
        count = Post.query.filter(
            func.date(Post.published_at) == day.isoformat()
        ).count()
        trend.append({"date": day.strftime("%m-%d"), "count": count})

    plugin_cards = []
    try:
        from app.plugins.manager import manager

        plugin_cards = manager.collect_dashboard_cards({"stats": stats})
    except Exception:
        pass

    health = health_service.badge()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        health=health,
        couple=couple,
        recent_posts=recent_posts,
        recent_moments=recent_moments,
        recent_backups=recent_backups,
        trend=trend,
        plugin_cards=plugin_cards,
        disk=backup_service.disk_usage(),
    )

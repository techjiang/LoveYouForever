"""示例插件：阅读足迹。

记录文章访问，在后台仪表盘给出「最受欢迎的文章」。
"""
from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Post
from app.plugins.base import Plugin

BP = Blueprint("reading_log", __name__, url_prefix="/plugin/reading-log")


@BP.route("/top")
def top_posts():
    posts = (
        Post.query.filter_by(status="published")
        .order_by(Post.views.desc())
        .limit(10)
        .all()
    )
    return jsonify([{"id": p.id, "title": p.title, "views": p.views} for p in posts])


class ReadingLogPlugin(Plugin):
    name = "reading_log"
    title = "阅读足迹"
    version = "1.0.0"
    author = "科技酱"
    description = "统计每篇文章被读了多少次，后台一眼看出哪篇最甜。"
    settings = [("count_once_per_session", "同一会话只计一次", "bool", True)]

    def register_blueprint(self):
        return BP

    def dashboard_cards(self, ctx: dict):
        posts = (
            Post.query.filter_by(status="published")
            .order_by(Post.views.desc())
            .limit(3)
            .all()
        )
        return [
            {
                "title": "阅读排行",
                "type": "list",
                "rows": [{"label": p.title, "value": p.views} for p in posts],
                "accent": "amber",
            }
        ]


PLUGIN = ReadingLogPlugin()

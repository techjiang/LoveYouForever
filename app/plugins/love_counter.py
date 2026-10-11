"""示例插件：在一起计时。

启用后在前台页脚显示「我们已经相爱 N 天 M 小时」。
"""
from flask import Blueprint, jsonify

from app.extensions import db
from app.models import Couple
from app.models.mixins import utcnow
from app.plugins.base import Plugin

BP = Blueprint("love_counter", __name__, url_prefix="/plugin/love-counter")

#: 注意：这里用纯字符串拼，不用 render_template_string。
#: footer_html 是在模板上下文处理器里被调用的，如果内部再渲染模板会无限递归。
TEMPLATE = (
    '<span class="lyf-plugin-love-counter" data-bound="{bound}">'
    '<span class="lc-clock">相爱 {days} 天 {hours} 小时 {minutes} 分</span>'
    "</span>"
)


@BP.route("/api")
def api_tick():
    couple = Couple.query.filter_by(sealed=True).first() or Couple.query.first()
    if not couple or not couple.bound_at:
        return jsonify({"days": 0, "hours": 0, "minutes": 0})
    delta = utcnow() - couple.bound_at
    total = int(delta.total_seconds())
    return jsonify({
        "days": total // 86400,
        "hours": (total % 86400) // 3600,
        "minutes": (total % 3600) // 60,
        "seconds": total % 60,
    })


class LoveCounterPlugin(Plugin):
    name = "love_counter"
    title = "相爱计时器"
    version = "1.0.0"
    author = "科技酱"
    description = "在页脚实时显示你们已经相爱了多少天多少小时，一秒钟都不马虎。"
    settings = [
        ("show_seconds", "显示秒（会一直跳动）", "bool", False),
    ]

    def register_blueprint(self):
        return BP

    def footer_html(self):
        couple = Couple.query.first()
        if not couple or not couple.bound_at:
            return ""
        delta = utcnow() - couple.bound_at
        total = int(delta.total_seconds())
        return TEMPLATE.format(
            bound=couple.bound_at.isoformat(),
            days=total // 86400,
            hours=(total % 86400) // 3600,
            minutes=(total % 3600) // 60,
        )

    def dashboard_cards(self, ctx: dict):
        couple = Couple.query.first()
        days = couple.days_together if couple else 0
        return [{"title": "相爱天数", "value": days, "unit": "天", "accent": "rose"}]


PLUGIN = LoveCounterPlugin()

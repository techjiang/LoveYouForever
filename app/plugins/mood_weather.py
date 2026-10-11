"""示例插件：心情天气。

给瞬间页加一个「今天的心情」小挂件，纯前端渲染。
"""
from flask import Blueprint, jsonify, request

from app.plugins.base import Plugin

BP = Blueprint("mood_weather", __name__, url_prefix="/plugin/mood-weather")

# 前端可选的天气集合，插件本身只做数据来源
WEATHERS = {
    "sunny": {"emoji": "☀️", "label": "晴", "tip": "像你笑起来的样子"},
    "cloudy": {"emoji": "⛅", "label": "多云", "tip": "有点想你"},
    "rainy": {"emoji": "🌧️", "label": "雨", "tip": "记得带伞，别淋着"},
    "snowy": {"emoji": "❄️", "label": "雪", "tip": "下雪了，想和你一起看"},
    "starry": {"emoji": "🌌", "label": "星空", "tip": "今晚的星星很像你的眼睛"},
}


@BP.route("/api")
def api_weather():
    key = request.args.get("mood", "sunny")
    data = WEATHERS.get(key, WEATHERS["sunny"])
    return jsonify({"key": key, **data, "all": list(WEATHERS.keys())})


class MoodWeatherPlugin(Plugin):
    name = "mood_weather"
    title = "心情天气"
    version = "1.0.0"
    author = "科技酱"
    description = "把今天的心情写成天气，挂在瞬间页顶上。"
    settings = [("default_mood", "默认心情", "str", "sunny")]

    def register_blueprint(self):
        return BP

    def nav_items(self):
        return []

    def footer_html(self):
        # 同样避免在上下文处理器里再渲染模板
        return (
            '<span class="lyf-mood-badge" data-plugin="mood_weather">'
            '<span class="mood-emoji">☀️</span> 今天心情很好</span>'
        )


PLUGIN = MoodWeatherPlugin()

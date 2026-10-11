"""插件基类与钩子常量。

插件就是放在 app/plugins/ 下的一个 .py 文件，定义 `PLUGIN` 变量指向一个
Plugin 子类实例。启用后会在这些钩子上被调用：

    on_install / on_enable / on_disable / on_uninstall
    before_request / after_request
    register_blueprint  -> 返回 Blueprint 或 None
    on_post_render(post, html) -> 可以二次加工文章 HTML
    dashboard_cards(ctx) -> 往后台仪表盘塞卡片数据
    nav_items() -> 往前台导航加菜单项
    footer_html() -> 往页脚塞内容
"""
from __future__ import annotations


class Plugin:
    name = "unnamed"
    title = "未命名插件"
    version = "1.0.0"
    author = ""
    description = ""
    #: 后台设置页里展示的配置字段 [(key, label, type, default)]
    settings = []

    def __init__(self, app=None):
        self.app = app
        self._config = {}

    # ---- 生命周期 ----
    def on_install(self, ctx=None):
        """第一次安装时调用，用来建表/写默认配置。"""

    def on_enable(self, ctx=None):
        """每次启用时调用。"""

    def on_disable(self, ctx=None):
        """停用时调用。"""

    def on_uninstall(self, ctx=None):
        """卸载时调用（数据是否保留由插件自己决定）。"""

    # ---- 请求钩子 ----
    def register_blueprint(self):
        return None

    def before_request(self):
        return None

    def after_request(self, response):
        return response

    # ---- 渲染钩子 ----
    def on_post_render(self, post, html: str) -> str:
        return html

    def nav_items(self):
        return []

    def footer_html(self):
        return ""

    def dashboard_cards(self, ctx: dict):
        """返回卡片列表，例如：
        {"title": "标题", "value": 12, "unit": "篇"}
        {"title": "排行", "rows": [{"label": "文章", "value": 3}]}

        注意：列表数据的键名用 rows，不要用 items
        （Jinja 里 dict.items 是方法，会冲突）。
        """
        return []

    # ---- 配置 ----
    def configure(self, config: dict):
        self._config = dict(config or {})

    def config(self, key, default=None):
        return self._config.get(key, default)

    # ---- 元信息 ----
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "settings": self.settings,
        }

# 插件开发

## 最小例子

```python
# app/plugins/hello.py
from app.plugins.base import Plugin

class HelloPlugin(Plugin):
    name = "hello"
    title = "你好插件"
    version = "1.0.0"
    description = "在页脚打个招呼"

    def footer_html(self):
        return '<span>今天也要开心呀</span>'

PLUGIN = HelloPlugin()
```

保存，刷新后台「插件」页，打开开关，重启一次。

## 生命周期钩子

| 钩子 | 时机 |
|---|---|
| `on_install(ctx)` | 第一次安装 |
| `on_enable(ctx)` | 每次启用 |
| `on_disable(ctx)` | 停用 |
| `on_uninstall(ctx)` | 卸载 |

`ctx` 里现在有 `{"app": Flask}`。

## 请求钩子

```python
def register_blueprint(self):
    return bp            # 返回 Blueprint 或 None

def before_request(self):
    pass                 # 每个请求前

def after_request(self, response):
    return response      # 每个请求后，必须返回 response
```

## 渲染钩子

```python
def on_post_render(self, post, html) -> str:
    """文章 HTML 渲染完之后过一遍。"""
    return html

def nav_items(self) -> list:
    """往导航栏加菜单。"""
    return [{"title": "我的页面", "url": "/plugin/hello", "kind": "plugin"}]

def footer_html(self) -> str:
    """页脚片段。"""
    return "<span>...</span>"

def dashboard_cards(self, ctx) -> list:
    """后台仪表盘卡片。"""
    return [{"title": "标题", "value": 12, "unit": "条"}]
```

## 配置

用 `settings` 声明，后台自动生成表单：

```python
settings = [
    ("message",  "问候语",   "str",  "你好"),
    ("count",    "条数",     "int",  5),
    ("enabled",  "是否开启", "bool", True),
]
```

读取：

```python
self.config("message")           # "你好"
self.config("count", 10)         # 带默认值
```

类型支持 `str` / `bool`，其他当字符串处理。

## 注意事项

这几条踩过坑，写下来免得你再踩。

### 不要在 `footer_html` 里渲染模板

`footer_html` 是在 Flask 的模板上下文处理器里被调用的。
如果你在里面再调 `render_template_string`，会触发上下文处理器 → 又调 `footer_html`
→ 无限递归 → 栈溢出。

拼字符串就行：

```python
def footer_html(self):
    return f'<span>{self.config("message")}</span>'
```

### 仪表盘列表用 `rows` 不用 `items`

Jinja 里 `card.items` 会解析成 dict 的 `items` 方法。用 `rows`：

```python
return [{"title": "排行", "rows": [{"label": "文章", "value": 3}]}]
```

### 插件出错不会拖垮整站

`manager.py` 里每个钩子调用都包了 try/except，出错只记日志。
但你也别滥用，该处理异常还是处理。

### 命名冲突

插件名会成为蓝图前缀和数据库记录的主键，别重名。
`base` / `manager` 是保留名。

## 内置插件当参考

| 插件 | 文件名 | 看点 |
|---|---|---|
| 相爱计时器 | `love_counter.py` | 页脚挂件 + 自己的 API + 仪表盘卡片 |
| 心情天气 | `mood_weather.py` | API 返回结构化数据给前端 |
| 阅读足迹 | `reading_log.py` | 仪表盘列表卡片 |

---

<div align="center">

**Powered by 科技酱 & LoveYouForever**

</div>

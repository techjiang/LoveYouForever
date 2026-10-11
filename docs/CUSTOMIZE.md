# 自定义指南

## 改主题配色

后台 → **主题配色**。

### 预设

| 名称 | 感觉 |
|---|---|
| 樱花粉 | 经典情侣粉 |
| 午夜玫瑰 | 深色，晚上看不刺眼 |
| 深海蓝 | 冷静克制，适合长文 |
| 抹茶绿 | 清爽自然 |
| 落日橘 | 温暖的黄昏 |
| 薰衣草 | 淡紫，安静浪漫 |

### 自己调

12 个色标，改完点「应用」立刻生效：

```
primary       主色（按钮、链接、强调）
primary_soft  主色浅底
accent        点缀色（爱心、标签）
bg            页面背景
surface       卡片背景
surface_alt   次级卡片背景
text          正文颜色
text_muted    次要文字
border        描边颜色
hero_from     首屏渐变起始
hero_to       首屏渐变结束
```

### 存成自己的主题

填个名字，点「另存为自定义主题」，会写进 `themes/你的名字.json`。

也可以直接手写：

```json
{
  "title": "我们的颜色",
  "description": "熬夜调出来的",
  "mode": "light",
  "colors": {
    "primary": "#7b61ff",
    "primary_soft": "#f0edff",
    "accent": "#ffb057",
    "bg": "#faf9ff",
    "surface": "#ffffff",
    "surface_alt": "#f4f2ff",
    "text": "#241f33",
    "text_muted": "#867f99",
    "border": "#e4dfff",
    "hero_from": "#a99bff",
    "hero_to": "#7b61ff"
  }
}
```

## 写文章

后台 → 文章 → 新建。左边写 Markdown，右边实时预览。

### 支持什么

标准 Markdown 之外：

- **代码高亮** —— 三个反引号 + 语言名
- **表格** —— 标准 Markdown 表格
- **脚注** —— `[^1]`
- **任务列表** —— `- [ ] 待办` / `- [x] 完成`
- **目录锚点** —— 标题自动生成，鼠标悬停出现 #
- **提示块** —— `!!! note "标题"`
- **图片灯箱** —— 正文图片点开自动放大

### 情侣彩蛋语法

```markdown
::love[你是我所有故事的开始]
```
高亮的情话，带下划线渐变。

```markdown
::vow[此生不负]
```
誓言块，居中、虚线边框。

```markdown
::couple[江 & 酱]
```
双人合体标记。

```markdown
::heart
```
跳动的心 ❤

### 署名

选了「共同署名」之后，文章会同时显示两个人的名字和称呼。
称呼来自用户的「关系称呼」字段，可以在注册时填，也可以随时改。

## 自定义页面

后台 → 页面 → 新建自定义页。

内容里可以插这两个占位符：

| 占位符 | 效果 |
|---|---|
| `{{latest_posts}}` | 最新 6 篇文章列表 |
| `{{albums}}` | 相册网格 |

适合做「我们的清单」「旅行地图」「读书清单」这类页面。

## 导航栏

内建页面和自定义页面都能勾「显示在导航栏」。
顺序由「排序」字段控制，数字小的排前面。

插件也能贡献导航项（`nav_items` 钩子）。

## 写插件

文件丢进 `app/plugins/`，刷新后台插件页就能看到。

```python
from app.plugins.base import Plugin
from flask import Blueprint

bp = Blueprint("my_bp", __name__, url_prefix="/plugin/my")

@bp.route("/hello")
def hello():
    return "hi"

class MyPlugin(Plugin):
    name = "my_plugin"
    title = "我的插件"
    version = "1.0.0"
    author = "你的名字"
    description = "一句话说明"
    settings = [
        ("message", "一句问候", "str", "你好呀"),
        ("enabled_extra", "开启彩蛋", "bool", False),
    ]

    def register_blueprint(self):
        return bp

    def footer_html(self):
        return f'<span>{self.config("message")}</span>'

    def nav_items(self):
        return [{"title": "我的页面", "url": "/plugin/my/hello", "kind": "plugin"}]

    def on_post_render(self, post, html):
        return html.replace("我", "咱们")

    def dashboard_cards(self, ctx):
        return [{"title": "我的数据", "value": 42, "unit": "个"}]

PLUGIN = MyPlugin()
```

### 需要注意

- 插件加载失败不会拖垮整站，只会记一条日志
- `footer_html` 里**不要调用 `render_template_string`** —— 它在模板上下文
  处理器里被调用，会无限递归。拼字符串就行。
- `dashboard_cards` 里列表数据的键名用 `rows`，不要用 `items`
  （Jinja 里 `dict.items` 是方法，会冲突）
- 配置字段用 `settings` 声明，后台自动生成表单

## 改文案

后台 → 站点设置：

- **基本信息** —— 站名、副标题、描述、Logo、备案
- **首页展示** —— 首屏标题、副标题、背景图、每页文章数
- **情侣设置** —— 关系名称、宣言
- **互动与评论** —— 评论开关、游客评论、开放注册

内建页面（关于我们 / 友链 / 留言板）在后台「页面」里可以直接改。

## 内容互联

三种方式，按优先级：

1. **手动指定** —— 文章编辑页填「相关文章 ID」
2. **标签重合** —— 按共同标签数量推荐
3. **同分类** —— 兜底

想关闭自动推荐，把「相关文章 ID」填个不存在的值即可（不推荐）。

---

<div align="center">

**Powered by 科技酱 & LoveYouForever**

</div>

<div align="center">

# 永远爱你 · LoveYouForever

**写给两个人的博客系统**

不是 CMS，是一个只属于你们的地方。

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-ff5c8a.svg)](#许可)

</div>

---

## 这是什么

一个情侣博客系统。两个人各自（或共同）写文章、发瞬间、传照片，
但这些内容在同一个屋檐下 —— 分类、归档、标签、内容互相连通。

它最在意的一件事是：**这段关系不会散**。

绑定成功后，没有解绑按钮，没有换人入口，API 层直接拒绝。
你可以再把关系「永封」一次 —— 之后连数据库层面都会写下不可逆指纹。
这不是营销话术，是写死在 `app/services/couple_service.py` 里的规则。

## 功能

### 你在意的

| | |
|---|---|
| **情侣绑定** | 一次性握手码 + 站点指纹校验，双方必须都跑这套系统 |
| **永生永世** | 绑定后不可解除、不可更换；可「永封」写入不可逆指纹 |
| **情侣约定** | 承诺 / 约法 / 愿望 / 契约，双方各自签名才生效，带内容指纹防篡改 |
| **内容合并** | 两个人的文章自动汇聚成一个共同空间，按时间排好 |
| **称呼系统** | 老公 / 老婆 / 男朋友 / 女朋友 / 随便你写，文章、瞬间、评论都会带上 |
| **门口寄语** | 首页顶上那一行字。今天想对 TA 说的话，随时能换，每天只露一条 |
| **共同瞬间** | 双人朋友圈，支持「一起发」，评论点赞都在共同空间里 |
| **内容互联** | 相关文章按手动指定 → 标签重合 → 同分类三级兜底 |
| **时间线** | 第一次见面、第一次旅行……都记下来 |
| **纪念日** | 生日、周年、下次见面的那天，首页替你们数着，不会数错 |

### 前台

首页 · 博客 · 文章详情 · 分类 · 分类列表 · 标签 · 标签云 · 归档 ·
相册 · 相册详情 · 瞬间流 · 瞬间时间线 · 瞬间详情 · 友链 · 关于 ·
留言板 · 自定义页面 · 搜索 · RSS · sitemap · 彩蛋页

### 后台

仪表盘（发布趋势 / 存储概览 / 插件卡片）· 文章（带 Markdown 实时预览）·
分类 · 标签 · 页面（内建 + 自定义）· 瞬间 · 评论 · 相册 · 友链 ·
小纸条 · 情侣关系 · 约定 · 时间线 · 纪念日 · 门口寄语 · 内容合并 ·
主题配色 · 插件 · 备份恢复 · 站点体检 · 用户 · 站点设置

### 细节

- **Markdown 美化** —— 代码高亮、表格、脚注、任务列表、目录锚点、图片灯箱
- **彩蛋语法** —— `::love[情话]`、`::vow[誓言]`、`::couple[合体标记]`、`::heart`
- **主题配色** —— 5 套预设 + 明暗模式 + 12 个色标自由调 + 存成自己的主题
- **插件生态** —— 把 `.py` 丢进 `app/plugins/` 就能用，10 个钩子
- **顶级备份** —— 在线 SQLite 快照 + tar.gz + SHA-256 校验 + 自动轮转 + 恢复前再备份
- **站点体检** —— 默认密码没改、站点地址没填、备份过期、磁盘将满……后台一眼看见哪不对，
  每条都附带「怎么修」。命令行 `flask doctor` 和后台共用同一套判断
- **零前端依赖** —— 没有 npm、没有构建步骤，改完刷新就见效

## 快速开始

### 小白模式

```bash
git clone https://github.com/techjiang/LoveYouForever.git
cd LoveYouForever
bash install.sh        # 一路回车
./start.sh
```

打开 `http://127.0.0.1:5000`，后台在 `/admin`。

### Docker

```bash
docker compose up -d
```

数据、备份、上传的图片都挂在宿主机目录，容器删了也不丢。

### 手动

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app wsgi:app init
python run.py
```

### 想要示例内容看效果？

```bash
flask --app wsgi:app seed                 # 只写内容，不造假的「另一半」
flask --app wsgi:app seed --with-partner  # 连演示账号一起建，方便看双人效果
```

## 情侣绑定怎么用

1. 两个人都部署好这套系统
2. A 登录 → `我们` → 生成握手码
3. 把码给 B
4. B 登录自己的站点 → 输入握手码 → 确认
5. 关系建立。**从此不可解除。**

如果两个人都想签个「生死状」，可以再点一次**永封**。
永封会把双方账号一起焊死，并写入基于成员 ID + 绑定时间 + 密钥的指纹。
之后任何改库的操作都会被 `detect_tamper()` 抓到。

## 插件怎么写

```python
# app/plugins/my_plugin.py
from app.plugins.base import Plugin

class MyPlugin(Plugin):
    name = "my_plugin"
    title = "我的插件"
    version = "1.0.0"
    description = "做点有意思的事"
    settings = [("greeting", "问候语", "str", "你好")]

    def footer_html(self):
        return f'<span>{self.config("greeting")}</span>'

    def on_post_render(self, post, html):
        return html.replace("你", "你们")

PLUGIN = MyPlugin()
```

可用钩子：`on_install` / `on_enable` / `on_disable` / `on_uninstall` /
`register_blueprint` / `before_request` / `after_request` /
`on_post_render` / `nav_items` / `footer_html` / `dashboard_cards`

仓库里带了三个示例：`love_counter`（相爱计时）、`mood_weather`（心情天气）、
`reading_log`（阅读足迹）。

## 备份

人生大事，这部分做得比功能还认真。

```bash
flask --app wsgi:app backup --note "升级前"   # 立即备份
flask --app wsgi:app backup-list              # 列出备份
flask --app wsgi:app restore 文件名            # 恢复（会先自动备份当前状态）
flask --app wsgi:app export                   # 导出 JSON
flask --app wsgi:app import 文件.json          # 导入
flask --app wsgi:app doctor                   # 体检
```

自动备份加进 crontab：

```cron
0 3 * * * cd /path/to/LoveYouForever && ./backup.sh "每日自动备份" >> logs/backup.log 2>&1
```

后台「备份」页也能一键操作：创建 / 下载 / 校验 / 恢复 / 删除 / 导入导出。

## 命令行

```bash
flask --app wsgi:app init             # 初始化
flask --app wsgi:app seed             # 写入演示数据
flask --app wsgi:app create-admin     # 新建管理员
flask --app wsgi:app reset-password   # 重置密码
flask --app wsgi:app doctor           # 体检
```

## 目录结构

```
app/
  __init__.py          应用工厂
  config.py            配置
  extensions.py        db / login / csrf
  models/              数据模型
  routes/              前台路由
  admin/               后台路由
  services/            业务逻辑（情侣规则、备份、主题）
  plugins/             插件系统 + 示例插件
  utils/               Markdown 渲染、工具函数
  templates/           Jinja2 模板
  static/              CSS / JS / 上传
themes/                用户自定义主题（JSON）
instance/              数据库、密钥
backups/               备份
docs/                  文档
```

## 常见问题

**忘了密码？**
```bash
flask --app wsgi:app reset-password
```

**能在两个服务器上互相绑定吗？**
可以。填好各自的「站点地址」，握手码通过任意方式传递即可。

**为什么没有解绑按钮？**
这是设计。规则在服务层，后台没暴露、API 也拒绝。

**纪念日和「在一起多少天」有什么区别？**
「在一起多少天」是往回数已经过去的日子；纪念日是往前数还有多久。
生日、周年这种每年都会再来一次，倒数日（领证、婚礼）过了就归档。

**换服务器怎么迁移？**
旧站 `flask export` → 新站 `flask import`，或者直接 `backup` / `restore`。

**上传的图片存在哪？**
`app/static/uploads/`。备份时可以选是否一起打包。

更多见 [`docs/`](docs/)。

## 许可

MIT

---

<div align="center">

**Powered by 科技酱 & LoveYouForever**

[科技酱](https://docs.asoe.cn) · [LoveYouForever](https://github.com/techjiang/LoveYouForever)

</div>

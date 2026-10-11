# API

目前主要是给「双方站点互连」用的开放接口，以及一些前端会用到的读取接口。

## 情侣互连

### `GET /couple/api/info`

返回本站的情侣信息，供对方站点展示互通。

```json
{
  "ok": true,
  "bound": true,
  "sealed": false,
  "name": "江 & 酱 的小窝",
  "slogan": "一生一世，永不分离",
  "days_together": 328,
  "members": [
    {"nickname": "阿江", "role": "老公", "avatar": ""},
    {"nickname": "小酱", "role": "老婆", "avatar": ""}
  ],
  "site": "永远爱你"
}
```

未绑定时：

```json
{"ok": true, "bound": false}
```

### `POST /couple/api/handshake`

对方站点用它校验握手码。

请求：

```json
{
  "token": "握手码",
  "site": "https://ta.example.com",
  "fingerprint": "对方站点指纹"
}
```

响应：

```json
{
  "ok": true,
  "issuer": "alice",
  "issuer_nickname": "小爱",
  "expires_at": "2026-10-14T05:00:00"
}
```

错误：

| 状态码 | 含义 |
|---|---|
| 400 | 缺少 token |
| 404 | token 不存在 |
| 410 | token 已使用或已过期 |

## 站点统计

### `GET /api/stats`

```json
{
  "posts": 42,
  "categories": 4,
  "tags": 18,
  "days_together": 328
}
```

## 上传

### `POST /upload`

需要登录。`multipart/form-data`。

| 字段 | 说明 |
|---|---|
| `file` | 图片文件 |
| `category` | `covers` / `photos` / `moments` / `avatars`，默认 `covers` |

响应：

```json
{"ok": true, "url": "/static/uploads/covers/ab12cd34.jpg", "filename": "ab12cd34.jpg"}
```

超过 2000px 宽的图会自动缩放。SVG / GIF / AVIF 不处理。

## 瞬间点赞

### `POST /moments/<id>/like`

带 `X-Requested-With: XMLHttpRequest` 时返回 JSON：

```json
{"ok": true, "liked": true, "count": 13}
```

重复调用会取消点赞（toggle 语义）。未登录用户按 IP 哈希去重。

## Markdown 预览

### `POST /admin/preview`

需要管理员。请求体：

```json
{"content": "# 标题\n\n正文"}
```

响应：

```json
{"html": "<h1 id=\"标题\">标题</h1>...", "minutes": 2}
```

## 插件

插件自己注册的蓝图，前缀统一 `"/plugin/<插件名>"`。
内置的三个：

| 插件 | 接口 |
|---|---|
| `love_counter` | `GET /plugin/love-counter/api` |
| `mood_weather` | `GET /plugin/mood-weather/api?mood=rainy` |
| `reading_log` | `GET /plugin/reading-log/top` |

## 订阅与索引

| 路径 | 内容 |
|---|---|
| `/feed.xml` | RSS 2.0，最新 20 篇 |
| `/sitemap.xml` | 所有已发布文章 |
| `/robots.txt` | 爬虫规则 |

---

<div align="center">

**Powered by 科技酱 & LoveYouForever**

</div>


## 门口寄语

### `GET /couple/api/wish`

首页顶上那一句，给「双方站点互连」用 —— 对方的站可以把它挂在自己门口。

```json
{
  "ok": true,
  "has_wish": true,
  "content": "今天也想你",
  "mood": "miss",
  "mood_label": "想你",
  "author": "阿江",
  "created_at": "2026-10-11T09:30:00",
  "is_today": true
}
```

没有任何寄语时：

```json
{"ok": true, "has_wish": false}
```

只返回公开的寄语。隐藏的那些不会出现在这里 —— 既然藏了，就不该从接口漏出去。

## 双站互连

两台机器互相拉内容。除了 `GET /couple/api/info`（公开），其余都建议带上
`X-LYF-Peer: <互连令牌>` 头 —— 令牌在后台「双站互连」页能看到。

### `GET /couple/peer/moments`

本机的公开瞬间。`?limit=20`（上限 50）。

```json
{"ok": true, "rows": [
  {"id": 1, "content": "今天也想你", "images": [], "mood": "🌙",
   "author": "小可爱", "created_at": "2026-10-11T08:17:51"}
]}
```

只出 `is_public=True` 的。隐藏的瞬间一条都不会出现。

### `GET /couple/peer/posts`

已发布的文章。

```json
{"ok": true, "rows": [
  {"id": 1, "title": "我们的第一个春天", "slug": "我们的第一个春天",
   "summary": "……", "author": "站长", "published_at": "2026-10-11T08:17:51",
   "url": "/post/我们的第一个春天"}
]}
```

### `GET /couple/peer/vows`

本机的约定。

### `GET /couple/peer/anniversaries`

本机记着的日子，带 `days_left`。

### `GET /couple/images/<name>`

对方站图片的本机缓存。`name` 是 32 位十六进制 + 扩展名，
由 `peer_service.fetch_image` 生成。其它形状一律 404。

### 握手接口

对方站点用 `POST /couple/api/handshake` 校验握手码，见上一节。

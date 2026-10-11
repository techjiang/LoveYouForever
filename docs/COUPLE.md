# 「永远爱你」是怎么实现的

这篇讲清楚项目里最核心的那套规则。

## 铁律

1. 一个账号只能绑定一段情侣关系
2. 双方都进入关系后，**不可解除、不可更换成员**
3. 「永封」之后连管理员也无法解绑
4. 以上三条由服务层强制，不是靠界面隐藏按钮

## 数据模型

```
User ──couple_id──> Couple <── user_a_id / user_b_id ── User
                      │
                      ├── Vow          约定（双方签名）
                      └── CoupleEvent  时间线
BindToken  一次性握手码
```

`Couple` 上还有：

- `sealed` / `sealed_at` —— 是否永封
- `seal_hash` —— 不可逆指纹
- `bound_at` —— 永恒计时起点

## 绑定流程

```
A 站                                     B 站
 │
 ├─ 生成 BindToken ──────────────────────┐
 │   带 site_url + site_fingerprint      │
 │                                       │
 │            （把 token 给 B）          │
 │                                       ▼
 │                              B 用自己账号输入 token
 │                                       │
 │                                       ├─ 校验 token 有效 / 未过期 / 未被用
 │                                       ├─ 校验 A 和 B 都 can_bind()
 │                                       ├─ 建 Couple，双方写入 couple_id
 │                                       └─ token 标记已用
 │
 └─ 关系建立，双方 bound_at 一致
```

对应代码：`app/services/couple_service.py`

- `create_bind_token(user, hours)` —— 生成，会作废该用户之前未用的 token
- `accept_bind_token(user, raw_token, partner_site)` —— 接受

开放接口在 `app/routes/couple.py`：

- `POST /couple/api/handshake` —— 对方站点校验 token
- `GET  /couple/api/info` —— 暴露本站情侣信息供对方展示

## 为什么「不可解除」

关键在 `User.can_bind()`：

```python
def can_bind(self) -> bool:
    """已经被绑定（尤其是已封存）的账号不允许再动关系。"""
    if self.sealed:
        return False
    c = self.couple
    return not (c and c.is_complete)
```

`create_bind_token` 和 `accept_bind_token` 进来第一件事就是检查它。
只要关系是完整的，两个入口全部关闭。

后台**没有**解绑路由 —— 不是忘了写，是刻意不写。

## 永封

```python
def seal_couple(couple, operator):
    if not couple.is_complete: raise CoupleError(...)
    if couple.sealed: return couple
    if operator.id not in (couple.user_a_id, couple.user_b_id):
        raise CoupleError("只有关系里的两个人才有资格永封。")

    couple.sealed = True
    couple.sealed_at = utcnow()
    couple.seal_hash = _seal_hash(couple)   # 指纹
    for u in couple.members:
        u.sealed = True                     # 双方账号一起焊死
```

指纹算法：

```python
sha256(f"{couple.id}:{couple.user_a_id}:{couple.user_b_id}:{couple.bound_at}:{SECRET_KEY[:16]}")
```

密钥在 `instance/secret_key` 里。换个部署环境，同一份数据算出来的指纹就不一样 ——
所以别人把数据库拷走改成员 ID，指纹立刻对不上。

## 篡改检测

```python
def detect_tamper(couple) -> bool:
    if not couple.sealed or not couple.seal_hash:
        return False
    return _seal_hash(couple) != couple.seal_hash
```

后台仪表盘和情侣页都会调它，对不上就顶一条红色横幅。

## 约定

```python
Vow:
  require_both   是否双方签名才生效
  signed_a_at / signed_b_at
  fingerprint    签名后锁定内容指纹
```

`sign_vow` 会根据调用者在关系里的位置（A 还是 B）写入对应的签名时间。
重复签名会被拒绝。

## 内容合并

```python
def merged_posts(couple, limit=None):
    ids = [couple.user_a_id, couple.user_b_id]
    return Post.query.filter(
        Post.status == "published",
        or_(Post.author_id.in_(ids), Post.co_author_id.in_(ids)),
    ).order_by(Post.published_at.desc())
```

前台 `/couple/merged`，后台 `/admin/couple/merged`。

## 称呼系统

`User.role_label` 存「老公」「老婆」「男朋友」或者任何自定义词。
`User.role_text` 是对外的显示值。

文章 `Post.owner_label` 在写入时快照当前称呼 —— 之后改称呼不会影响历史文章。

显示逻辑：

```python
@property
def author_line(self):
    return " & ".join(
        f"{a.display_name}（{a.role_text}）" if a.role_text else a.display_name
        for a in self.authors
    )
```

## 共同署名

`Post.co_author_id` / `Moment.co_author_id`。
非空表示两个人一起写 / 一起发，页面上显示双方名字。

瞬间页还有个「一起发」的勾选项。

---

<div align="center">

**Powered by 科技酱 & LoveYouForever**

</div>

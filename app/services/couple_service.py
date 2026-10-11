"""情侣关系服务层：「永远爱你」的全部规则都在这里。

铁律（产品需求，不可通过任何界面绕过）：
1. 一个账号只能绑定一段情侣关系；
2. 双方都进入关系后（is_complete），关系不可解除、不可更换成员；
3. 一旦「永封」，连管理员也无法解绑，数据库只接受纪念日与约定的追加。
"""
import hashlib
import secrets
from datetime import timedelta

from flask import current_app, url_for
from sqlalchemy import or_

from app.extensions import db
from app.models import BindToken, Couple, CoupleEvent, SiteSetting, User, Vow
from app.models.mixins import utcnow
from app.utils.helpers import slugify


class CoupleError(Exception):
    """业务规则冲突。"""


# --------------------------------------------------------------------------
# 站点指纹：用来验证「对方确实也用的是本博客系统」
# --------------------------------------------------------------------------
def site_fingerprint(url: str = "") -> str:
    raw = f"LoveYouForever|{url or ''}|{current_app.config['SECRET_KEY'][:16]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def site_url() -> str:
    return SiteSetting.get("site_url", "") or ""


# --------------------------------------------------------------------------
# 绑定
# --------------------------------------------------------------------------
def create_bind_token(user: User, hours: int = 72) -> BindToken:
    if not user.can_bind():
        raise CoupleError("你已经处在不可解除的关系里了，不能再次发起绑定。")

    # 作废该用户之前没用的 token，保证同时只有一个有效握手码
    BindToken.query.filter_by(issuer_id=user.id, used=False).update({"used": True})

    token = BindToken(
        token=secrets.token_urlsafe(24),
        issuer_id=user.id,
        site_url=site_url(),
        site_fingerprint=site_fingerprint(site_url()),
        expires_at=utcnow() + timedelta(hours=hours),
    )
    db.session.add(token)
    db.session.commit()
    return token


def accept_bind_token(user: User, raw_token: str, partner_site: str = "") -> Couple:
    """接受对方的握手码，建立关系。

    partner_site 是发起方站点地址，用于双向验证。
    """
    if not user.can_bind():
        raise CoupleError("你已经处在不可解除的关系里了，不能接受绑定。")

    token = BindToken.query.filter_by(token=raw_token.strip()).first()
    if token is None:
        raise CoupleError("握手码不存在，请检查是否复制完整。")
    if not token.alive:
        raise CoupleError("握手码已使用或已过期，请让对方重新生成。")

    issuer = db.session.get(User, token.issuer_id)
    if issuer is None:
        raise CoupleError("发起方账号已不存在。")
    if issuer.id == user.id:
        raise CoupleError("不能和自己绑定哦。")
    if not issuer.can_bind():
        raise CoupleError("对方已经处在不可解除的关系里了。")

    couple = Couple(
        name=f"{issuer.display_name} & {user.display_name}",
        slogan=SiteSetting.get("couple_slogan", "愿我们一生一世，永不分离"),
        user_a_id=issuer.id,
        user_b_id=user.id,
        bound_at=utcnow(),
        theme_color=SiteSetting.get("theme_color", "#ff5c8a"),
    )
    db.session.add(couple)
    db.session.flush()

    issuer.couple_id = couple.id
    user.couple_id = couple.id

    token.used = True
    token.used_by_id = user.id
    token.used_at = utcnow()

    # 自动补一条时间线
    db.session.add(
        CoupleEvent(
            couple_id=couple.id,
            title="我们绑定啦",
            detail=f"{issuer.display_name} 与 {user.display_name} 从此在同一片屋檐下。",
            happened_on=utcnow().date(),
            kind="milestone",
        )
    )
    db.session.commit()

    # 把「在一起」这天自动记成一个纪念日，用户不用自己再建一遍
    try:
        from app.services import anniversary_service

        anniversary_service.seed_defaults(couple)
    except Exception:  # 纪念日建不出来也不该挡住绑定
        db.session.rollback()

    return couple


def seal_couple(couple: Couple, operator: User) -> Couple:
    """永封关系：把两个人的账号也一起焊死。

    这一步之后：
    - couple.user_a_id / user_b_id 不允许再变
    - 双方 user.couple_id 不允许再变
    - 生成不可逆指纹，任何试图篡改成员的操作都会被 detect_tamper 抓到
    """
    if not couple.is_complete:
        raise CoupleError("双方都还没到齐，不能永封。")
    if couple.sealed:
        return couple
    if operator.id not in (couple.user_a_id, couple.user_b_id):
        raise CoupleError("只有关系里的两个人才有资格永封。")

    couple.sealed = True
    couple.sealed_at = utcnow()
    couple.seal_hash = _seal_hash(couple)

    for u in couple.members:
        u.sealed = True
        u.sealed_at = couple.sealed_at

    db.session.add(
        CoupleEvent(
            couple_id=couple.id,
            title="永生永世 · 已封存",
            detail="我们的关系被写进了数据库的骨头里，从此不可解除。",
            happened_on=utcnow().date(),
            kind="milestone",
        )
    )
    db.session.commit()
    return couple


def _seal_hash(couple: Couple) -> str:
    raw = f"{couple.id}:{couple.user_a_id}:{couple.user_b_id}:{couple.bound_at}:{current_app.config['SECRET_KEY'][:16]}"
    return hashlib.sha256(raw.encode()).hexdigest()


def detect_tamper(couple: Couple) -> bool:
    """检查关系是否被外部直接改库篡改过。返回 True 表示指纹对不上。"""
    if not couple.sealed or not couple.seal_hash:
        return False
    return _seal_hash(couple) != couple.seal_hash


# --------------------------------------------------------------------------
# 约定
# --------------------------------------------------------------------------
def sign_vow(vow: Vow, user: User) -> Vow:
    couple = db.session.get(Couple, vow.couple_id)
    if not couple or user.id not in (couple.user_a_id, couple.user_b_id):
        raise CoupleError("你不在这段关系里，签不了这份约定。")

    if user.id == couple.user_a_id:
        if vow.signed_a_at:
            raise CoupleError("你已经签过啦。")
        vow.signed_a_at = utcnow()
    else:
        if vow.signed_b_at:
            raise CoupleError("你已经签过啦。")
        vow.signed_b_at = utcnow()

    vow.fingerprint = vow_fingerprint(vow)
    db.session.commit()
    return vow


def vow_fingerprint(vow: Vow) -> str:
    raw = f"{vow.id}:{vow.title}:{(vow.content or '')[:200]}:{vow.signed_a_at}:{vow.signed_b_at}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def create_vow(couple: Couple, title: str, content: str, kind: str = "promise", require_both: bool = True) -> Vow:
    vow = Vow(
        couple_id=couple.id,
        title=title.strip(),
        content=content,
        kind=kind,
        require_both=require_both,
    )
    db.session.add(vow)
    db.session.commit()
    return vow


# --------------------------------------------------------------------------
# 内容合并：把两个人的文章聚到一个「共同空间」
# --------------------------------------------------------------------------
def merged_posts(couple: Couple, limit: int | None = None):
    """取双方的所有已发布文章，按时间倒序 —— 这是「情侣所有文章内容合并」的实现。"""
    from app.models import Post

    ids = [i for i in (couple.user_a_id, couple.user_b_id) if i]
    q = Post.query.filter(
        Post.status == "published",
        or_(Post.author_id.in_(ids), Post.co_author_id.in_(ids)),
    ).order_by(Post.published_at.desc())
    return q.limit(limit) if limit else q


def couple_stats(couple: Couple) -> dict:
    from app.models import Album, Moment, Photo, Post

    ids = [i for i in (couple.user_a_id, couple.user_b_id) if i]
    posts = Post.query.filter(Post.author_id.in_(ids), Post.status == "published").count()
    moments = Moment.query.filter(Moment.author_id.in_(ids)).count()
    photos = Photo.query.join(Album).count()
    vows = Vow.query.filter_by(couple_id=couple.id).count()
    events = CoupleEvent.query.filter_by(couple_id=couple.id).count()
    return {
        "days": couple.days_together,
        "posts": posts,
        "moments": moments,
        "photos": photos,
        "vows": vows,
        "events": events,
        "sealed": couple.sealed,
    }

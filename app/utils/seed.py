"""演示数据：第一次装好之后不至于是一个空壳。"""
from app.extensions import db
from app.models import (
    Album, Category, CoupleEvent, CustomPage, FriendLink, Moment, Photo, Post,
    SiteSetting, Tag, User,
)
from app.utils.helpers import slugify
from app.utils.markdown_render import extract_summary, reading_minutes, render

DEMO_POSTS = [
    ("我们的第一个春天", "日常", "春天来的时候，我们一起去看了樱花。\n\n::love[你说樱花落下来的样子像雪]\n\n那天风很大，你把围巾分了一半给我。", ["春天", "日常"]),
    ("关于「永远」这件事", "纪念日", "有人说永远太远了。\n\n::vow[但我愿意用余生去证明这四个字]\n\n永远不是时间长度，是一个决定。", ["纪念日", "心情"]),
    ("周末厨房记", "美食", "第一次一起做饭，厨房像打仗一样。\n\n- 番茄炒蛋有点咸\n- 你说很好吃\n\n我知道你在骗我，但我很开心。", ["美食", "日常"]),
    ("海边的第三天", "旅行", "早上五点起来看日出，你困得睁不开眼还是陪我去了。\n\n> 有些风景，只有和你一起看才叫风景。\n\n下次还去吗？", ["旅行", "海边"]),
    ("写在深夜", "日常", "今天加班到很晚，回家看到你给我留的灯。\n\n::love[那一刻觉得，一切都值得]\n", ["深夜", "日常"]),
    ("我们的一年", "纪念日", "一年前的今天，我们在这个站上绑定了彼此。\n\n时间过得真快，快到我还没来得及细数。", ["周年", "纪念日"]),
]

DEMO_MOMENTS = [
    ("今天路过那家奶茶店，想起你上次说要去试试。下次一起。", "☕"),
    ("刚下班，下雨了，没带伞。", "🌧️"),
    ("拍到了很好看的晚霞，分享给你。", "🌇"),
    ("周末想去看电影，有没有想看的？", "🎬"),
]


def seed_demo() -> None:
    if Post.query.count() > 0:
        return

    from app.services import site_service

    admin = User.query.filter_by(is_admin=True).first() or User.query.first()
    if admin is None:
        return

    # 一个虚拟的另一半，让页面看起来是「两个人」
    partner = User.query.filter_by(username="partner").first()
    if partner is None:
        partner = User(username="partner", nickname="小可爱", role_label="老婆", bio="被爱的人 也在爱着")
        partner.set_password("loveyou")
        db.session.add(partner)
        db.session.commit()

    couple = None
    from app.models import Couple

    if Couple.query.count() == 0:
        couple = Couple(
            name=f"{admin.display_name} & {partner.display_name}",
            slogan=site_service.get("couple_slogan", "一生一世，永不分离"),
            user_a_id=admin.id,
            user_b_id=partner.id,
            bound_at=__import__("app.models.mixins", fromlist=["utcnow"]).utcnow(),
        )
        db.session.add(couple)
        db.session.flush()
        admin.couple_id = couple.id
        partner.couple_id = couple.id
        admin.role_label = admin.role_label or "老公"
        db.session.commit()

    cats = {c.name: c for c in Category.query.all()}
    for name in {p[1] for p in DEMO_POSTS}:
        if name not in cats:
            c = Category(name=name, slug=slugify(name), sort_order=len(cats))
            db.session.add(c)
            db.session.flush()
            cats[name] = c

    for i, (title, cat, body, tags) in enumerate(DEMO_POSTS):
        author = admin if i % 2 == 0 else partner
        post = Post(
            title=title,
            slug=slugify(title),
            content_md=body,
            content_html=render(body),
            summary=extract_summary(body),
            category_id=cats[cat].id,
            author_id=author.id,
            status="published",
            reading_minutes=reading_minutes(body),
            owner_label=author.role_text,
        )
        post.tags = [_ensure_tag(t) for t in tags]
        db.session.add(post)

    for content, mood in DEMO_MOMENTS:
        db.session.add(
            Moment(
                content=content,
                mood=mood,
                author_id=admin.id if DEMO_MOMENTS.index((content, mood)) % 2 == 0 else partner.id,
                co_authored=False,
            )
        )

    album = Album(title="我们的相册", slug="our-album", description="随手拍下来的日常", location="家里")
    db.session.add(album)
    db.session.flush()
    for title in ["夕阳", "早餐", "猫", "书桌", "雨天", "旅行"]:
        db.session.add(Photo(album_id=album.id, url=f"/static/img/demo/{slugify(title)}.svg", caption=title))

    for name, url, desc in [
        ("科技酱的文档", "https://docs.asoe.cn", "本站作者的技术文档站"),
        ("LoveYouForever", "https://github.com/techjiang/LoveYouForever", "情侣博客开源项目"),
    ]:
        db.session.add(FriendLink(name=name, url=url, description=desc, is_approved=True))

    db.session.add(
        CustomPage(
            title="我们的清单",
            slug="our-list",
            content_md="## 想一起做的事\n\n- [ ] 去看一次海\n- [ ] 一起做一顿完整的饭\n- [ ] 养一只猫\n\n{{latest_posts}}\n",
            content_html=render("## 想一起做的事\n\n- [ ] 去看一次海\n- [ ] 一起做一顿完整的饭\n- [ ] 养一只猫\n\n{{latest_posts}}\n"),
            show_in_nav=True,
        )
    )
    db.session.commit()


def _ensure_tag(name: str) -> Tag:
    tag = Tag.query.filter_by(name=name).first()
    if tag is None:
        tag = Tag(name=name, slug=slugify(name))
        db.session.add(tag)
        db.session.flush()
    return tag

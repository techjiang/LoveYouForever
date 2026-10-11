"""核心行为测试。

重点覆盖「永远爱你」那套不可逆规则 —— 这是项目最不能出错的地方。
运行：python -m pytest tests/ -v
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def app(tmp_path):
    """每个测试一个独立数据库。

    配置在 create_app 之前塞进 config.json 的替代方案：直接用环境变量，
    并且用完就删掉，避免测试之间相互污染。
    """
    db_path = tmp_path / "test.db"
    os.environ["LYF_DATABASE_URI"] = f"sqlite:///{db_path}"
    os.environ["LYF_ENV"] = "development"

    # 清掉可能被上一个测试污染的模块缓存
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    from app import create_app

    application = create_app("development")
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    yield application

    os.environ.pop("LYF_DATABASE_URI", None)
    for mod in list(sys.modules):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth(app):
    with app.app_context():
        from app.extensions import db
        from app.models import User

        def make(username, **kw):
            u = User(username=username, nickname=kw.pop("nickname", username), **kw)
            u.set_password("pass1234")
            db.session.add(u)
            db.session.commit()
            return u.id

        yield make


# --------------------------------------------------------------------- 基础
def test_homepage_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "科技酱" in r.get_data(as_text=True)


def test_locked_signature_on_every_page(client):
    """全局锁定署名必须在全站底部出现。"""
    html = client.get("/").get_data(as_text=True)
    assert 'data-lyf-signature="locked"' in html
    assert "Powered by" in html
    assert 'href="https://docs.asoe.cn"' in html
    assert 'href="https://github.com/techjiang/LoveYouForever"' in html


def test_404(client):
    assert client.get("/definitely-not-here").status_code == 404


def test_api_stats(client):
    assert client.get("/api/stats").status_code == 200


# --------------------------------------------------------------------- 情侣
def test_bind_rejects_self(app, client, auth):
    """不能和自己绑定。"""
    from app.extensions import db
    from app.models import User
    from app.services import couple_service

    uid = auth("solo")
    with app.app_context():
        user = db.session.get(User, uid)
        token = couple_service.create_bind_token(user)
        with pytest.raises(couple_service.CoupleError):
            couple_service.accept_bind_token(user, token.token)


def test_bind_locks_after_complete(app, auth):
    """绑定完成后不能再发起或接受绑定。"""
    from app.extensions import db
    from app.models import User
    from app.services import couple_service

    a_id = auth("a1")
    b_id = auth("b1")
    with app.app_context():
        a = db.session.get(User, a_id)
        b = db.session.get(User, b_id)
        token = couple_service.create_bind_token(a)
        couple = couple_service.accept_bind_token(b, token.token)
        assert couple.is_complete

        assert not a.can_bind()
        assert not b.can_bind()
        with pytest.raises(couple_service.CoupleError):
            couple_service.create_bind_token(b)


def test_token_single_use(app, auth):
    """握手码只能用一次。"""
    from app.extensions import db
    from app.models import User
    from app.services import couple_service

    a_id = auth("a2")
    b_id = auth("b2")
    c_id = auth("c2")
    with app.app_context():
        a = db.session.get(User, a_id)
        b = db.session.get(User, b_id)
        c = db.session.get(User, c_id)
        token = couple_service.create_bind_token(a)
        couple_service.accept_bind_token(b, token.token)
        with pytest.raises(couple_service.CoupleError):
            couple_service.accept_bind_token(c, token.token)


def test_seal_is_irreversible(app, auth):
    """永封之后指纹可校验，成员不能再改。"""
    from app.extensions import db
    from app.models import Couple, User
    from app.services import couple_service

    a_id = auth("a3")
    b_id = auth("b3")
    with app.app_context():
        a = db.session.get(User, a_id)
        b = db.session.get(User, b_id)
        token = couple_service.create_bind_token(a)
        couple = couple_service.accept_bind_token(b, token.token)
        couple_service.seal_couple(couple, a)

        couple = Couple.query.first()
        assert couple.sealed
        assert couple.seal_hash
        assert not couple_service.detect_tamper(couple)

        # 篡改成员 -> 指纹对不上
        couple.user_b_id = None
        db.session.commit()
        assert couple_service.detect_tamper(couple)


def test_cannot_seal_incomplete(app, auth):
    from app.extensions import db
    from app.models import Couple, User
    from app.services import couple_service

    a_id = auth("a4")
    with app.app_context():
        a = db.session.get(User, a_id)
        couple = Couple(name="half", user_a_id=a.id)
        db.session.add(couple)
        db.session.commit()
        with pytest.raises(couple_service.CoupleError):
            couple_service.seal_couple(couple, a)


# --------------------------------------------------------------------- 内容
def test_markdown_love_syntax():
    from app.utils.markdown_render import render

    html = render("::love[我爱你]\n\n::vow[永不分离]\n\n::heart")
    assert 'class="lyf-love"' in html
    assert 'class="lyf-vow"' in html
    assert "lyf-heart" in html


def test_markdown_strips_script():
    from app.utils.markdown_render import render

    html = render('<script>alert("xss")</script>\n\n正文')
    assert "<script>" not in html
    assert "正文" in html


def test_reading_minutes():
    from app.utils.markdown_render import reading_minutes

    assert reading_minutes("") == 1
    assert reading_minutes("中" * 800) >= 2


def test_slugify():
    from app.utils.helpers import slugify

    assert slugify("Hello World") == "hello-world"
    assert slugify("我们的春天") == "我们的春天"
    assert slugify("") == "item"


# --------------------------------------------------------------------- 备份
def test_backup_and_verify(app):
    from app.services import backup_service

    with app.app_context():
        rec = backup_service.create_backup(kind="test", note="pytest")
        assert rec.filename.endswith(".tar.gz")
        assert rec.size_bytes > 0
        result = backup_service.verify_backup(rec.filename)
        assert result["ok"] is True


def test_export_json(app):
    from app.services import backup_service

    with app.app_context():
        payload = backup_service.export_json()
        assert "tables" in payload
        assert "SiteSetting" in payload["tables"]
        # 密码不该被导出去
        for row in payload["tables"].get("User", []):
            assert "password_hash" not in row


# --------------------------------------------------------------------- 主题
def test_theme_resolve(app):
    from app.services import theme_service

    colors = theme_service.resolve_colors("sakura")
    assert colors["primary"].startswith("#")

    overridden = theme_service.resolve_colors("sakura", {"primary": "#123456"})
    assert overridden["primary"] == "#123456"


def test_all_themes_have_required_tokens(app):
    from app.services import theme_service

    for key, theme in theme_service.all_themes().items():
        for token in theme_service.COLOR_TOKENS:
            assert token in theme["colors"], f"{key} 缺少 {token}"


# ----------------------------------------------------------------- 纪念日
def _make_anniversary(app, title, anchor, **kw):
    from app.services import anniversary_service

    with app.app_context():
        from app.models import Anniversary, Couple

        couple = Couple.query.first()
        a = anniversary_service.create(couple, title, anchor, **kw)
        return a.id


def test_yearly_anniversary_rolls_to_next_year(app):
    """每年重复的日子，过了今年就该指向明年，而不是显示负数。"""
    from datetime import date

    from app.models import Anniversary
    from app.services import anniversary_service

    with app.app_context():
        anchor = date(2020, 5, 20)
        a = anniversary_service.create(None, "周年", anchor, repeat_yearly=True)

        # 锚点当天：就是今天
        assert a.days_left(date(2026, 5, 20)) == 0
        # 锚点次日：指向明年 5/20
        assert a.days_left(date(2026, 5, 21)) == 364 or a.days_left(date(2026, 5, 21)) == 365
        # 永远是正数
        assert a.days_left(date(2030, 1, 1)) > 0
        assert a.next_date(date(2026, 5, 21)) == date(2027, 5, 20)


def test_one_off_countdown_expires(app):
    """一次性的倒数日，过了就没有下一次。"""
    from datetime import date

    from app.services import anniversary_service

    with app.app_context():
        a = anniversary_service.create(None, "领证", date(2026, 12, 31), repeat_yearly=False)
        assert a.days_left(date(2026, 12, 1)) == 30
        assert a.days_left(date(2026, 12, 31)) == 0
        assert a.days_left(date(2027, 1, 1)) is None
        assert "已过去" in anniversary_service.humanize(a, date(2027, 1, 1))


def test_leap_day_anniversary_does_not_crash(app):
    """2/29 出生的人，在平年不能被除零/值错误打死。"""
    from datetime import date

    from app.services import anniversary_service

    with app.app_context():
        a = anniversary_service.create(None, "闰日生日", date(2000, 2, 29))
        left = a.days_left(date(2026, 3, 1))
        assert left is not None and left > 0


def test_anniversary_ordering_pins_today_first(app):
    """今天的排最前，置顶其次，剩下的按天数升序。"""
    from datetime import date, timedelta

    from app.services import anniversary_service

    with app.app_context():
        today = date.today()
        anniversary_service.create(None, "很久以后", today + timedelta(days=200))
        anniversary_service.create(None, "明天", today + timedelta(days=1))
        anniversary_service.create(None, "就是今天", today)

        items = anniversary_service.list_all(None)
        assert items[0].title == "就是今天"
        assert items[1].title == "明天"

        stats = anniversary_service.stats(None)
        assert stats["today"] == 1
        assert stats["next"].title == "明天"


def test_binding_seeds_first_anniversary(app):
    """绑定之后首页不该是空的，自动记下「我们在一起」。"""
    from app.services import anniversary_service, couple_service

    with app.app_context():
        from app.extensions import db
        from app.models import User

        a = User(username="a", nickname="A")
        a.set_password("pass1234")
        b = User(username="b", nickname="B")
        b.set_password("pass1234")
        db.session.add_all([a, b])
        db.session.commit()

        token = couple_service.create_bind_token(a)
        couple = couple_service.accept_bind_token(b, token.token)

        assert couple.is_complete
        items = anniversary_service.list_all(couple)
        assert len(items) == 1
        assert items[0].title == "我们在一起"
        assert items[0].is_pinned


def test_seed_does_not_invent_partner(app):
    """默认 seed 不该凭空造一个「小可爱」出来。"""
    from app.utils.seed import seed_demo

    with app.app_context():
        from app.models import User

        # bootstrap 已经建好了默认 admin，直接拿来用
        admin = User.query.filter_by(is_admin=True).first()
        assert admin is not None

        seed_demo()  # 默认不建假人

        assert User.query.filter_by(username="partner").first() is None
        from app.models import Post

        posts = Post.query.all()
        assert posts, "演示文章还是应该写入"
        assert all(p.author_id == admin.id for p in posts)


def test_homepage_never_leaks_anniversaries(app, client):
    """首页是公开的，纪念日只属于两个人，不该出现在门外。"""
    from datetime import date, timedelta

    from app.extensions import db
    from app.models import Couple, User
    from app.services import anniversary_service

    with app.app_context():
        u = User(username="solo", nickname="Solo")
        u.set_password("pass1234")
        db.session.add(u)
        db.session.commit()
        c = Couple(name="我们")
        db.session.add(c)
        db.session.commit()
        anniversary_service.create(c, "她的生日", date.today() + timedelta(days=9))

    html = client.get("/").get_data(as_text=True)
    assert "她的生日" not in html
    assert "值得数着的日子" not in html


def test_homepage_has_no_setup_wizard(app, client):
    """首页不是安装向导：空站就说空站，别教人改密码、别催人绑定。"""
    html = client.get("/").get_data(as_text=True)
    assert "改掉默认密码" not in html
    assert "和对方绑定" not in html
    assert "还没有文章" in html


def test_homepage_does_not_pretend_a_couple(app, client):
    """没有另一半的时候，首页不该摆出「我们的小站」这种不存在的戏。"""
    html = client.get("/").get_data(as_text=True)
    assert "我们的小站" not in html
    assert "天相伴" not in html


# ------------------------------------------------------------------- 门口寄语
def test_wish_only_shows_one(app, client):
    """门口那句只露一条，不然首页就不是首页了。"""
    from app.extensions import db
    from app.models import User
    from app.services import wish_service

    with app.app_context():
        u = User.query.first()
        wish_service.post(u, "第一条")
        wish_service.post(u, "第二条")

    html = client.get("/").get_data(as_text=True)
    assert "第二条" in html
    assert "第一条" not in html


def test_wish_hidden_from_guests_when_private(app, client):
    """关掉公开之后，未登录的人不该看到。"""
    from app.extensions import db
    from app.models import DailyWish, User
    from app.services import wish_service

    with app.app_context():
        u = User.query.first()
        w = wish_service.post(u, "悄悄话")
        w.is_public = False
        db.session.commit()

    assert "悄悄话" not in client.get("/").get_data(as_text=True)


def test_wish_strips_empty(app):
    """空话贴不上去。"""
    from app.models import User
    from app.services import wish_service

    with app.app_context():
        u = User.query.first()
        assert wish_service.post(u, "   ") is None
        assert wish_service.current() is None


def test_wish_requires_login(client):
    """游客不能贴。"""
    r = client.post("/couple/wish", data={"content": "随便写"}, follow_redirects=False)
    assert r.status_code in (302, 401)


# ------------------------------------------------------------------- 情侣页
def test_couple_wall_shows_recent_wishes(app, client):
    """情侣页的墙上要有最近几条，谁贴的、什么时候贴的都要看得见。"""
    from app.extensions import db
    from app.models import User
    from app.services import couple_service, wish_service

    with app.app_context():
        a = User(username="wa", nickname="甲")
        a.set_password("pass1234")
        b = User(username="wb", nickname="乙")
        b.set_password("pass1234")
        db.session.add_all([a, b])
        db.session.commit()
        tok = couple_service.create_bind_token(a)
        couple_service.accept_bind_token(b, tok.token)
        wish_service.post(a, "墙上的一句")

    client.post("/auth/login", data={"username": "wa", "password": "pass1234"})
    html = client.get("/couple/").get_data(as_text=True)
    assert "门口的墙" in html
    assert "墙上的一句" in html


def test_couple_wall_requires_couple(client):
    """还没绑定的人进情侣页会被引导去绑定，而不是报错。"""
    r = client.get("/couple/")
    assert r.status_code == 302


# ------------------------------------------------------------------- 站点体检
def test_health_flags_default_password(app):
    """默认密码必须被标成 error —— 这是最容易被忽略、后果最大的一条。"""
    from app.services import health_service

    with app.app_context():
        report = health_service.run_all()
        titles = {r["title"]: r for r in report["rows"]}
        assert any("默认密码" in t for t in titles), titles.keys()
        item = next(r for k, r in titles.items() if "默认密码" in k)
        assert item["level"] == "error"
        assert item["fix"], "报错要给出怎么修"
        assert report["errors"] >= 1


def test_health_warns_missing_backup_and_site_url(app):
    from app.services import health_service

    with app.app_context():
        rows = {r["title"]: r["level"] for r in health_service.run_all()["rows"]}
        assert rows.get("站点地址没填") == "warn"
        assert rows.get("一次备份都没有") == "warn"


def test_health_ok_after_setup(app):
    """把该配的都配好之后，不该再有 error。"""
    from app.extensions import db
    from app.models import SiteSetting, User
    from app.services import backup_service, health_service

    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        admin.set_password("a-much-better-password")
        SiteSetting.set("site_url", "https://love.example.com")
        db.session.commit()
        backup_service.create_backup(kind="test", note="health")

        report = health_service.run_all()
        assert report["errors"] == 0, [r for r in report["rows"] if r["level"] == "error"]


def test_health_page_requires_admin(client):
    """体检结果里有配置细节，不能给游客看。"""
    r = client.get("/admin/health", follow_redirects=False)
    assert r.status_code in (302, 401, 403)


def test_admin_pages_render(app, client):
    """后台几个新页面至少要能打开，别 500。"""
    client.post("/auth/login", data={"username": "admin", "password": "loveyou"})
    for path in ("/admin/", "/admin/health", "/admin/wishes"):
        assert client.get(path).status_code == 200, path


def test_wish_api_hides_private(app, client):
    """隐藏的寄语不该从接口漏出去。"""
    from app.extensions import db
    from app.models import User
    from app.services import wish_service

    with app.app_context():
        u = User.query.first()
        w = wish_service.post(u, "这是藏起来的")
        w.is_public = False
        db.session.commit()

    data = client.get("/couple/api/wish").get_json()
    assert data["has_wish"] is False


def test_wish_api_shape(app, client):
    from app.models import User
    from app.services import wish_service

    with app.app_context():
        wish_service.post(User.query.first(), "今天也想你", "miss")

    data = client.get("/couple/api/wish").get_json()
    assert data["has_wish"] is True
    assert data["content"] == "今天也想你"
    assert data["mood_label"] == "想你"


# ------------------------------------------------------------------- 双站互连
def test_peer_disconnected_by_default(app, client):
    """两台机器不是天生就通的，得自己去连。"""
    from app.services import peer_service

    with app.app_context():
        s = peer_service.summary()
        assert s["connected"] is False
        assert s["conn"] is None
        assert s["total"] == 0

    html = client.get("/").get_data(as_text=True)
    assert "TA 那边的动静" not in html


def test_peer_rejects_self_and_empty(app):
    """填自己的地址或者什么都不填，都应该被挡下来。"""
    from app.extensions import db
    from app.models import SiteSetting
    from app.services import peer_service
    from app.services.peer_service import PeerError

    with app.app_context():
        SiteSetting.set("site_url", "https://mine.example.com")
        db.session.commit()
        with pytest.raises(PeerError):
            peer_service.connect("")
        with pytest.raises(PeerError):
            peer_service.connect("https://mine.example.com")


def test_peer_reports_unreachable(app):
    """连不上的地址要给一句人话，而不是抛异常出来。"""
    from app.services import peer_service

    with app.app_context():
        info = peer_service.fetch_peer("http://127.0.0.1:9")
        assert info["ok"] is False
        assert info["message"]


def test_peer_demo_shows_up_but_only_when_connected(app, client):
    """演示互连的内容，只在「连着」的时候出现在首页。"""
    from app.services import peer_service

    with app.app_context():
        peer_service.seed_demo_peer()

    html = client.get("/").get_data(as_text=True)
    assert "TA 那边的动静" in html

    with app.app_context():
        peer_service.disconnect()
    html = client.get("/").get_data(as_text=True)
    assert "TA 那边的动静" not in html


def test_peer_disconnect_does_not_touch_relationship(app):
    """断开互连 ≠ 解绑。这是最容易被人误解的一条，必须锁死。"""
    from app.extensions import db
    from app.models import Couple, PeerConnection, User
    from app.services import couple_service, peer_service

    with app.app_context():
        a = User(username="lover_a", nickname="阿江")
        a.set_password("pass1234")
        b = User(username="lover_b", nickname="小酱")
        b.set_password("pass1234")
        db.session.add_all([a, b])
        db.session.commit()

        token = couple_service.create_bind_token(a)
        couple = couple_service.accept_bind_token(b, token.token)
        assert couple.is_complete

        peer_service.seed_demo_peer()
        peer_service.disconnect()

        still = db.session.get(Couple, couple.id)
        assert still is not None
        assert still.user_a_id == a.id and still.user_b_id == b.id
        assert a.can_bind() is False, "断开互连之后也不该能重新绑定"


def test_peer_mirror_never_duplicates(app):
    """同一条内容同步多少次都只留一行。"""
    from app.services import peer_service

    with app.app_context():
        peer_service.seed_demo_peer()
        first = peer_service.summary()["total"]
        peer_service.seed_demo_peer()
        assert peer_service.summary()["total"] == first


def test_peer_image_blocks_path_traversal(app, client):
    """图片代理只认缓存文件名，别被人拿来读服务器上的文件。"""
    for bad in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "secret.txt", "abc.png"):
        assert client.get(f"/couple/images/{bad}").status_code == 404


def test_peer_api_needs_token_when_configured(app, client):
    """配了令牌之后，外人拉不走内容。"""
    from app.services import peer_service

    with app.app_context():
        token = peer_service.summary()["my_token"]

    ok = client.get("/couple/peer/moments", headers={"X-LYF-Peer": token})
    assert ok.status_code == 200
    assert ok.get_json()["ok"] is True

    bad = client.get("/couple/peer/moments", headers={"X-LYF-Peer": "wrong-token"})
    assert bad.status_code == 403


def test_peer_api_hides_private_moments(app, client):
    """互连接口不能把私密瞬间漏出去。"""
    from app.extensions import db
    from app.models import Couple, Moment, User
    from app.services import peer_service

    with app.app_context():
        u = User.query.first()
        c = Couple(name="我们", user_a_id=u.id, user_b_id=u.id)
        db.session.add(c)
        db.session.commit()
        db.session.add(Moment(content="公开的瞬间", author_id=u.id, is_public=True))
        db.session.add(Moment(content="只给自己看的", author_id=u.id, is_public=False))
        db.session.commit()
        rows = peer_service.outgoing_moments()
        texts = [r["content"] for r in rows]
        assert "公开的瞬间" in texts
        assert "只给自己看的" not in texts


def test_peer_admin_requires_admin(client):
    r = client.get("/admin/peer")
    assert r.status_code in (302, 401, 403)


def test_peer_admin_page_renders(app, client):
    from app.services import peer_service

    with app.app_context():
        peer_service.seed_demo_peer()

    client.post("/auth/login", data={"username": "admin", "password": "loveyou"})
    r = client.get("/admin/peer")
    assert r.status_code == 200
    assert "双站互连" in r.get_data(as_text=True)


# ------------------------------------------------------------------- 演示数据
def test_seed_is_incremental_not_all_or_nothing(app):
    """seed 必须是补全：bootstrap 已经建过分类/页面，也不该因此写不进演示内容。"""
    from app.utils.seed import seed_demo

    with app.app_context():
        from app.models import Category, CustomPage, Post

        # bootstrap 建的默认分类和页面先躺在那儿 —— 早先的实现就是被它们挡住的
        assert Category.query.count() > 0
        assert CustomPage.query.count() == 0

        first = seed_demo()
        assert first["posts"] > 0
        assert Post.query.count() == first["posts"]

        second = seed_demo()
        assert sum(second.values()) == 0, "第二遍不该再写一遍"
        assert Post.query.count() == first["posts"]


def test_seed_keeps_writing_missing_pieces(app):
    """分类被清掉一部分之后，seed 应该把缺的补回来，而不是整块跳过。"""
    from app.utils.seed import seed_demo

    with app.app_context():
        from app.extensions import db
        from app.models import CustomPage, Photo

        seed_demo()
        before = Photo.query.count()
        CustomPage.query.delete()
        db.session.commit()

        stats = seed_demo()
        assert stats["pages"] == 1
        assert Photo.query.count() == before, "已有的照片不该被删掉或重写"


# ------------------------------------------------------------------- 邮件提醒
def test_mail_silent_without_smtp(app):
    """没配 SMTP 就什么都不做 —— 提醒失败不该影响站点。"""
    from app.models import Couple, User
    from app.services import mail_service

    with app.app_context():
        assert mail_service.is_configured() is False
        assert mail_service.maybe_send_daily(None) is False
        u = User.query.first()
        c = Couple(name="我们", user_a_id=u.id, user_b_id=u.id)
        assert mail_service.send("someone@example.com", "标题", "正文") is False


def test_mail_digest_lists_due_items(app):
    """今天/明天的日子要出现在提醒里。"""
    from datetime import timedelta

    from app.extensions import db
    from app.models import Couple, User
    from app.services import anniversary_service, mail_service
    from app.models.mixins import utcnow

    with app.app_context():
        u = User.query.first()
        c = Couple(name="我们", user_a_id=u.id, user_b_id=u.id)
        db.session.add(c)
        db.session.commit()

        anniversary_service.create(c, "她的生日", (utcnow() + timedelta(days=2)).date(), kind="birthday")
        anniversary_service.create(c, "明年的事", (utcnow() + timedelta(days=200)).date())

        items = mail_service.due_items(c)
        titles = [a.title for a in items]
        assert "她的生日" in titles
        assert "明年的事" not in titles

        subject, body, html = mail_service.build_digest(c, items)
        assert "她的生日" in subject
        assert "她的生日" in body
        assert "LoveYouForever" in html

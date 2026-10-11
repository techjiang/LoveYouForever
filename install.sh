#!/usr/bin/env bash
# ============================================================================
#  LoveYouForever 一键安装脚本
#
#  用法：
#    bash install.sh                     # 交互式安装（推荐）
#    bash install.sh --yes               # 全默认，无人值守
#    bash install.sh --port 8080         # 指定端口
#    bash install.sh --env production    # 生产模式
#
#  小白也能用：跟着提示一路回车就行。
# ============================================================================
set -euo pipefail

APP_NAME="LoveYouForever"
GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; RED=$'\033[0;31m'; CYAN=$'\033[0;36m'; BOLD=$'\033[1m'; NC=$'\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PORT=""
ENV_MODE=""
ASSUME_YES=0
SKIP_VENV=0

# ------------------------------------------------------------------ 参数解析
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --env) ENV_MODE="$2"; shift 2 ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    --no-venv) SKIP_VENV=1; shift ;;
    -h|--help)
      sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数：$1"; exit 1 ;;
  esac
done

banner() {
  echo ""
  echo "${CYAN}  ❤  ${BOLD}${APP_NAME}${NC}${CYAN} 安装程序${NC}"
  echo "${CYAN}  一个写给两个人的博客系统${NC}"
  echo ""
}

info()  { echo "${GREEN}  ✔${NC} $*"; }
warn()  { echo "${YELLOW}  !${NC} $*"; }
fail()  { echo "${RED}  ✘${NC} $*" >&2; exit 1; }
step()  { echo ""; echo "${BOLD}▸ $*${NC}"; }

ask() {
  # ask <提示> <默认值>
  local prompt="$1" default="$2" answer=""
  if [[ $ASSUME_YES -eq 1 ]]; then echo "$default"; return; fi
  read -r -p "  $prompt [$default]: " answer </dev/tty || true
  echo "${answer:-$default}"
}

ask_secret() {
  local prompt="$1" default="$2" answer=""
  if [[ $ASSUME_YES -eq 1 ]]; then echo "$default"; return; fi
  read -r -s -p "  $prompt: " answer </dev/tty || true
  echo "" >&2
  echo "${answer:-$default}"
}

banner

# ------------------------------------------------------------------ 1. 检查环境
step "检查运行环境"

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver=$("$candidate" -c 'import sys;print("%d%d"%sys.version_info[:2])' 2>/dev/null || echo 0)
    if [[ "$ver" -ge 39 ]]; then PYTHON_BIN="$candidate"; break; fi
  fi
done
[[ -n "$PYTHON_BIN" ]] || fail "没有找到 Python 3.9+，请先安装：https://www.python.org/downloads/"
info "Python: $($PYTHON_BIN -V 2>&1) ($PYTHON_BIN)"

command -v git >/dev/null 2>&1 && info "Git: $(git --version)" || warn "没有 git（不影响运行）"

# ------------------------------------------------------------------ 2. 交互配置
step "站点配置"
if [[ -z "$ENV_MODE" ]]; then
  ENV_MODE="$(ask "运行模式 (development/production)" "production")"
fi
[[ -z "$PORT" ]] && PORT="$(ask "监听端口" "5000")"
SITE_NAME="$(ask "站点名称" "永远爱你")"
SITE_URL="$(ask "站点地址（可留空，之后再改）" "")"
ADMIN_USER="$(ask "管理员用户名" "admin")"
ADMIN_NICK="$(ask "你的昵称" "站长")"
ADMIN_PASS="$(ask_secret "管理员密码（留空则自动生成）" "")"

if [[ -z "$ADMIN_PASS" ]]; then
  ADMIN_PASS="$("$PYTHON_BIN" -c 'import secrets;print(secrets.token_urlsafe(12))')"
  GENERATED_PASS=1
else
  GENERATED_PASS=0
fi

if [[ $SKIP_VENV -eq 1 ]]; then
  USE_VENV="n"
else
  USE_VENV="$(ask "创建独立虚拟环境（推荐）(y/n)" "y")"
fi

# ------------------------------------------------------------------ 3. 虚拟环境
step "准备 Python 环境"

PY_RUN="$PYTHON_BIN"
if [[ "$USE_VENV" =~ ^[Yy] ]]; then
  if [[ ! -d .venv ]]; then
    "$PYTHON_BIN" -m venv .venv || fail "创建虚拟环境失败，请检查是否安装了 python3-venv"
    info "已创建虚拟环境 .venv"
  else
    info "复用已有的 .venv"
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  PY_RUN="python"
fi

"$PY_RUN" -m pip install --upgrade pip -q 2>/dev/null || true
info "安装依赖……（第一次会慢一点）"
"$PY_RUN" -m pip install -q -r requirements.txt \
  || fail "依赖安装失败。可以试试国内镜像：
    $PY_RUN -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
info "依赖安装完成"

# ------------------------------------------------------------------ 4. 目录
step "创建必要目录"
mkdir -p instance backups themes logs
mkdir -p app/static/uploads/{covers,photos,moments,avatars}
for d in covers photos moments avatars; do touch "app/static/uploads/$d/.gitkeep"; done
info "instance/ backups/ themes/ 已就绪"

# ------------------------------------------------------------------ 5. 初始化
step "初始化数据库与站点"
export LYF_ENV="$ENV_MODE"
export FLASK_APP="wsgi:app"

"$PY_RUN" - <<PYEOF
import os, sys
sys.path.insert(0, os.getcwd())
from app import create_app
from app.extensions import db
app = create_app("$ENV_MODE")
with app.app_context():
    from app.models import SiteSetting, User
    from app.services import site_service
    db.create_all()
    from app.services.bootstrap import init_site
    init_site(app)
    site_service.save_settings({
        "site_name": """$SITE_NAME""",
        "site_url": """$SITE_URL""",
    })
    # 系统里如果只有默认 admin，就用用户填的信息替换掉密码
    admin = User.query.filter_by(username="admin").first()
    if admin is not None:
        admin.username = """$ADMIN_USER"""
        admin.nickname = """$ADMIN_NICK"""
        admin.set_password("""$ADMIN_PASS""")
        admin.is_admin = True
        db.session.commit()
        print("ADMIN_READY")
    else:
        u = User.query.filter_by(username="""$ADMIN_USER""").first()
        if u is None:
            u = User(username="""$ADMIN_USER""", nickname="""$ADMIN_NICK""", is_admin=True)
            db.session.add(u)
        u.set_password("""$ADMIN_PASS""")
        db.session.commit()
        print("ADMIN_READY")
PYEOF
info "数据库初始化完成"

# ------------------------------------------------------------------ 6. 启动脚本
step "生成启动脚本"

cat > start.sh <<STARTEOF
#!/usr/bin/env bash
# 启动 LoveYouForever（开发模式：python 内置服务器）
set -e
cd "\$(dirname "\${BASH_SOURCE[0]}")"
[[ -d .venv ]] && source .venv/bin/activate
export LYF_ENV="${ENV_MODE}"
export PORT="${PORT}"
exec python run.py
STARTEOF
chmod +x start.sh

cat > start-prod.sh <<STARTEOF
#!/usr/bin/env bash
# 启动 LoveYouForever（生产模式：gunicorn）
set -e
cd "\$(dirname "\${BASH_SOURCE[0]}")"
[[ -d .venv ]] && source .venv/bin/activate
export LYF_ENV=production
export PORT="${PORT}"
WORKERS=\${WORKERS:-4}
if python -c "import gunicorn" 2>/dev/null; then
  exec gunicorn -w "\$WORKERS" -k gthread --threads 4 -b "0.0.0.0:${PORT}" --access-logfile - wsgi:app
else
  echo "未安装 gunicorn，改用内置服务器（仅适合小流量）"
  exec python wsgi.py
fi
STARTEOF
chmod +x start-prod.sh

cat > backup.sh <<BACKUPEOF
#!/usr/bin/env bash
# 备份 LoveYouForever。可加进 crontab 定时执行。
set -e
cd "\$(dirname "\${BASH_SOURCE[0]}")"
[[ -d .venv ]] && source .venv/bin/activate
export LYF_ENV="${ENV_MODE}"
export FLASK_APP=wsgi:app
flask backup --note "\${1:-手动备份}"
BACKUPEOF
chmod +x backup.sh

info "start.sh / start-prod.sh / backup.sh 已生成"

# ------------------------------------------------------------------ 7. 完成
echo ""
echo "${GREEN}${BOLD}  ✨ 安装完成！${NC}"
echo ""
echo "  ${BOLD}访问地址${NC}   http://127.0.0.1:${PORT}"
echo "  ${BOLD}后台地址${NC}   http://127.0.0.1:${PORT}/admin"
echo "  ${BOLD}用户名${NC}     ${ADMIN_USER}"
if [[ "${GENERATED_PASS:-0}" -eq 1 ]]; then
  echo "  ${BOLD}密码${NC}       ${YELLOW}${ADMIN_PASS}${NC}  ${YELLOW}(自动生成，请立刻修改)${NC}"
else
  echo "  ${BOLD}密码${NC}       你刚才设置的那个"
fi
echo ""
echo "  启动：  ${CYAN}./start.sh${NC}          （开发 / 小流量）"
echo "          ${CYAN}./start-prod.sh${NC}     （生产，需要 gunicorn）"
echo "  备份：  ${CYAN}./backup.sh${NC}          （建议加进 crontab）"
echo ""
echo "  提示：记得把「站点地址」填对，情侣绑定和 RSS 都靠它。"
echo ""
echo "  ${CYAN}Powered by 科技酱 & LoveYouForever${NC}"
echo ""

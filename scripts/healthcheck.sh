#!/usr/bin/env bash
# 简单的健康检查，适合放进监控。
# 用法：bash scripts/healthcheck.sh http://127.0.0.1:5000
set -euo pipefail

BASE="${1:-http://127.0.0.1:5000}"
FAIL=0

check() {
  local url="$1" label="$2"
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$url" || echo "000")
  if [[ "$code" == "200" ]]; then
    echo "  ok   $label ($code)"
  else
    echo "  FAIL $label ($code)"
    FAIL=1
  fi
}

echo "检查 $BASE"
check "$BASE/" "首页"
check "$BASE/api/stats" "统计接口"
check "$BASE/auth/login" "登录页"
check "$BASE/feed.xml" "RSS"

if [[ $FAIL -eq 0 ]]; then
  echo "全部正常"
else
  echo "有检查项失败"
  exit 1
fi

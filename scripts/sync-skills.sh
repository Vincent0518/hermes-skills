#!/usr/bin/env bash
# sync-skills.sh — 把本地 ~/.hermes/skills/** 镜像进本仓库 skills/ 并推送到 GitHub（local→GitHub 版本管理/备份）
# 由 Hermes cron 定时调用(no_agent)。本地 skills 是源头真相，仓库是版本管理与备份。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$HOME/.hermes/skills"
DST="$REPO_DIR/skills"
cd "$REPO_DIR"

[ -d "$SRC" ] || { echo "source skill dir missing: $SRC (skip)"; exit 0; }
mkdir -p "$DST"

# 镜像：--delete 清理已删 skill；排除备份/候选/缓存/系统垃圾
rsync -a --delete \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.bak*' \
  --exclude='*.repair-candidate' \
  --exclude='.DS_Store' \
  "$SRC/" "$DST/"

# 有变更才提交推送
if git diff --quiet -- skills/; then
  echo "no skill changes; nothing to push ($(date '+%F %T'))"
else
  NAME="$(git config user.name 2>/dev/null || echo Vincent0518)"
  EMAIL="$(git config user.email 2>/dev/null || echo 217146640+Vincent0518@users.noreply.github.com)"
  git add skills/
  git -c user.name="$NAME" -c user.email="$EMAIL" commit -m "Sync skills: $(date '+%Y-%m-%d %H:%M')"
  git push origin main
  echo "pushed sync $(date '+%F %T')"
fi

#!/usr/bin/env bash
# sync-skills.sh — 白名单制同步：只把 scripts/allowlist.txt 里列出的 skill 同步到 GitHub。
# 每批上传前先过安全门禁(scripts/scan-secrets.py: 密钥/口令/内网IP/MAC)，检出即中止、不推送。
# 本地 ~/.hermes/skills 是源头真相，仓库只含白名单内的 skill（版本管理+备份）。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_ROOT="$HOME/.hermes/skills"
DST="$REPO_DIR/skills"
SCAN="$REPO_DIR/scripts/scan-secrets.py"
ALLOWLIST="$REPO_DIR/scripts/allowlist.txt"
cd "$REPO_DIR"

# 读白名单(忽略空行/#注释) —— macOS bash 3.2 无 mapfile，用 while-read
SYNC_SKILLS=()
while IFS= read -r line; do
  case "$line" in ''|\#*) continue ;; esac
  SYNC_SKILLS+=("$line")
done < "$ALLOWLIST"

[ -d "$SRC_ROOT" ] || { echo "本地 skill 根目录缺失: $SRC_ROOT"; exit 1; }

echo "== ① 安全门禁: 扫描 ${#SYNC_SKILLS[@]} 个白名单 skill 源头 =="
for s in "${SYNC_SKILLS[@]}"; do
  src="$SRC_ROOT/$s"
  if [ ! -d "$src" ]; then
    echo "!! 白名单项在本地不存在: $s (跳过)"
    continue
  fi
  python3 "$SCAN" "$src" || { echo "!! [$s] 未通过安全门禁 —— 中止，不推送。"; exit 1; }
done

echo "== ② 重建 skills/（只含白名单，清掉非授权内容） =="
rm -rf "$DST"
mkdir -p "$DST"
for s in "${SYNC_SKILLS[@]}"; do
  src="$SRC_ROOT/$s"
  [ -d "$src" ] || continue
  mkdir -p "$DST/$(dirname "$s")"
  rsync -a --exclude='__pycache__/' --exclude='*.pyc' --exclude='*.bak*' \
        --exclude='*.repair-candidate' --exclude='.DS_Store' "$src/" "$DST/$s/"
  echo "   + $s"
done

echo "== ③ 变更检测 + 提交推送 =="
if [ -z "$(git status --porcelain -- skills/ scripts/allowlist.txt)" ]; then
  echo "no skill changes; nothing to push ($(date '+%F %T'))"
  exit 0
fi
git add skills/ scripts/allowlist.txt
git -c user.name="$(git config user.name 2>/dev/null || echo Vincent0518)" \
    -c user.email="$(git config user.email 2>/dev/null || echo 217146640+Vincent0518@users.noreply.github.com)" \
    commit -m "Sync skills: $(date '+%Y-%m-%d %H:%M')"
git push origin main
echo "pushed sync $(date '+%F %T')"

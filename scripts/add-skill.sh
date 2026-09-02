#!/usr/bin/env bash
# add-skill.sh <skill路径(相对 ~/.hermes/skills)> — 把新 skill 加入上传白名单并同步一次。
# 例: scripts/add-skill.sh my-new-skill     (顶层)
#     scripts/add-skill.sh reasoning/xxx    (带分类)
# 加入前先跑安全门禁；检出密钥/口令/内网IP/MAC 会中止并提示位置。
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL="${1:-}"
SCAN="$REPO_DIR/scripts/scan-secrets.py"
ALLOWLIST="$REPO_DIR/scripts/allowlist.txt"

[ -n "$SKILL" ] || { echo "用法: add-skill.sh <skill路径>"; exit 2; }
SRC="$HOME/.hermes/skills/$SKILL"
[ -d "$SRC" ] || { echo "本地不存在该 skill: $SRC"; exit 1; }

echo "== ① 安全门禁扫描 $SKILL =="
python3 "$SCAN" "$SRC" || { echo "!! $SKILL 未通过门禁 —— 请清理敏感项后再试。"; exit 1; }

echo "== ② 加入白名单 =="
if grep -qxF "$SKILL" "$ALLOWLIST"; then
  echo "已在白名单: $SKILL"
else
  echo "$SKILL" >> "$ALLOWLIST"
  echo "已加入 allowlist.txt: $SKILL"
fi

echo "== ③ 执行同步 =="
"$REPO_DIR/scripts/sync-skills.sh"

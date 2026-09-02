# Hermes Skills (版本管理集合仓库)

用户**精选** Hermes skill 的版本管理仓库。**只上传白名单内、且通过安全门禁的 skill**（用户铁律 2026-09-02）。

## ⚠️ 上传规则（铁律）

1. **白名单制**：只同步 `scripts/allowlist.txt` 里列出的 skill——不是全量镜像。
2. **安全门禁**：任何待上传 skill 不得含：
   - API KEY / 令牌（`sk-*`、`AKIA*`、`ghp_*`、`AIza*` 等真值）
   - 口令 / secret 赋值（占位示例 `xxx...`、env 引用不算）
   - 内网 / 环路 / Tailscale IP（`10.x`、`192.168.x`、`172.16-31.x`、`127.x`、`169.254.x`、`100.64/10`）
   - MAC 地址
   - 检出即**中止推送**并报 file:line。
3. 本地 `~/.hermes/skills` 是源头真相；仓库只含白名单 skill 的干净副本。

## 目录结构

```
skills/                        ← 只含 allowlist 内的 skill
  cabinet-review/              ← 内阁机制（Hermes 任议长，独立真实调 Qwen + Codex 两名阁员）
  reasoning/
    long-session-auto-continuation/   ← 长会话自动续接链路手册
scripts/
  allowlist.txt                ← ★ 上传白名单（一行一个，相对 ~/.hermes/skills 的路径）
  add-skill.sh <name>          ← ★ 把新 skill 加白名单并同步（先过门禁）
  sync-skills.sh               ← 白名单同步：门禁 → 重建 skills/ → 提交推送
  scan-secrets.py              ← 安全门禁扫描器（密钥/口令/内网IP/MAC）
.github/workflows/
  sync-skills.yml              ← GitHub Actions：安全门禁 + frontmatter 校验（双保险）
```

## 常用操作

```bash
# 把新 skill 放上去（自动过门禁 + 加白名单 + 推送）
scripts/add-skill.sh my-skill-name          # 顶层 skill
scripts/add-skill.sh reasoning/xxx          # 带分类的 skill

# 手动跑一次同步
scripts/sync-skills.sh

# 单独扫描某个 skill 是否含敏感项（不上传也随时可用）
python3 scripts/scan-secrets.py ~/.hermes/skills/某个skill
```

## 自动同步

Hermes cron `Skills→GitHub sync`（每 30 分钟）跑 `sync-skills.sh`：本地白名单 skill 有变更即自动过门禁并推送。

## 变更

- 2026-09-02：初始建立；收录 `cabinet-review` + `long-session-auto-continuation`。
- 2026-09-02：改为**白名单制 + 安全门禁**（清除 cabinet SKILL.md 内网 IP `100.108.177.1`）；Actions 加安全扫描步。

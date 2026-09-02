# Hermes Skills (版本管理集合仓库)

用户自定义 Hermes skill 的**版本管理仓库**。本地 `~/.hermes/skills/` 是源头真相，本仓库为版本管理与备份，通过「本地自动同步脚本 + GitHub Actions 校验流水线」维护。

## 目录结构

```
skills/                 ← 本地 ~/.hermes/skills/** 的镜像
  cabinet-review/       ← 内阁机制（Hermes 任议长，独立真实调 Qwen + Codex 两名阁员）
  reasoning/
    long-session-auto-continuation/   ← 长会话自动续接链路手册
scripts/
  sync-skills.sh        ← 本地自动同步脚本（镜像 + 提交 + 推送）
.github/workflows/
  sync-skills.yml       ← GitHub Actions 校验流水线
```

## 已收录 skill

| skill | 说明 |
|-------|------|
| `cabinet-review` | 内阁评估：Hermes 本体任议长，机器独立真实调用 Qwen 与 Codex 两名阁员（有上下文、可查证） |
| `long-session-auto-continuation` | 长会话自动续接链路：达阈值 → 压缩总结 → 记 Obsidian → 开续接子会话 → 读 Obsidian 继续 |

## 自动同步流水线（双向概念）

- **本地自动同步**（真正的 local→GitHub）：Hermes cron 定时跑 `scripts/sync-skills.sh`，把 `~/.hermes/skills/**` 镜像到 `skills/` 并提交推送。本地一改，仓库自动跟进。
- **GitHub Actions 校验**（仓库侧门禁）：每次推送 `skills/**`，`sync-skills.yml` 校验每个 `SKILL.md` 的 frontmatter（name/description 必填、description ≤60 字符预算、name 与目录一致）。不合规会在工作流里标红。

## 手动同步

```bash
scripts/sync-skills.sh
```

## 变更

- 2026-09-02：初始建立；收录 `long-session-auto-continuation` 与 `cabinet-review`；加入同步脚本 + Actions 校验流水线。

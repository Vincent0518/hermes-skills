# Hermes Skills · 目录 / 索引

> 已分享的 Hermes skill 一览。**每个 skill 一个独立公开仓库**，点进去即可单独下载/安装你要的那一个（无需克隆整个集合）。

## 收录的 skill

| Skill | 说明 | 仓库 |
|-------|------|------|
| **cabinet-review** | 内阁评估：Hermes 本体任议长，机器独立真实调用 Qwen 与 Codex 两名阁员做独立分析再汇总裁决 | [Vincent0518/cabinet-review](https://github.com/Vincent0518/cabinet-review) |
| **long-session-auto-continuation** | 长会话自动续接链路：达阈值 → 自动压缩总结 → 记 Obsidian → 开续接子会话 → 读 Obsidian 继续 | [Vincent0518/long-session-auto-continuation](https://github.com/Vincent0518/long-session-auto-continuation) |

## 如何下载 / 安装某个 skill

```bash
git clone <对应仓库链接>
mkdir -p ~/.hermes/skills/<skill路径>
cp -r <克隆目录>/* ~/.hermes/skills/<skill路径>/
```

具体路径与说明见各仓库自己的 README。

## 上传规则（作者侧铁律）

- **白名单制**：只有作者显式放进允许名单的 skill 才会出现并分享。
- **安全门禁**：每个 skill 仓库自带 `.github/workflows/security-gate.yml`，推送/PR 都会跑 `scripts/scan-secrets.py`，检出 **API KEY / 口令 / 内网·Tailscale IP / MAC** 即拒绝——确保公开内容无敏感信息。

## 维护

- 自动同步：本地 `~/.hermes/skills/` 里允许名单内的 skill 变更，由 Hermes cron 过门禁后自动推送到各自仓库，并刷新本索引页。

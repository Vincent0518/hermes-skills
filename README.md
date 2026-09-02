# long-session-auto-continuation

Hermes skill — 长会话自动续接链路手册：达阈值 → 自动压缩总结 → 记录到 Obsidian → 自动开续接子会话 → 新会话读取继续。

## 内容

- **链路对照**：直觉 vs Hermes 实际（续跑靠会话内注入的压缩摘要，Obsidian 是记录/桥）
- **五环节实现速查表**：每环节实现 + 状态
- **关键路径速查**：config 行号、watcher 脚本/cron id、插件路径、日记 `.raw.md` 后缀、state.db
- **验证命令**：4 条可复跑检查链路的 SQL/grep
- **排障要点**：踩坑记录
- **诊断注意事项**：哨兵暂停、watcher 调度 lag

## 相关

- `session-lifecycle-governance` — 阈值驱动治理哲学 / 双阈值 / 哨兵设计
- `hermes-compression-ops` — 压缩机制源码级诊断
- `project-context-milestones` — 六字段快照 + 里程碑换会话

## 变更

- v1.0.0 — 初始版本（2026-09-02）

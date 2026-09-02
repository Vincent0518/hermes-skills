---
name: long-session-auto-continuation
description: "Use when checking the long-session auto-continuation chain."
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [session, life cycle, compression, continuation, obsidian, handoff]
    related_skills: [session-lifecycle-governance, hermes-compression-ops, project-context-milestones]
---

# 长会话自动续接链路 (Long-Session Auto Continuation)

**触发**: 想搞清楚「会话长到阈值后如何自动总结、记录到 Obsidian、开新会话、然后新会话接着之前的任务」这套链路时加载。

> ⚠️ 与 `session-lifecycle-governance` 的分工：本 skill 是**这条自动链路的操作手册**(怎么工作/在哪/怎么验证/怎么排障)；那个 skill 讲的是**治理哲学**(阈值驱动非定时、双阈值、哨兵设计)。两者互补勿混。

## 这条链在做什么(与你直觉的对照)

你的直觉: `达阈值→自动总结→记到Obsidian→自动开新会话→读Obsidian→继续任务`

Hermes 实际: 任务交接主体走**会话内注入的压缩摘要**，Obsidian 是持久化记录+跨工具桥。细微差别：
- **达阈值→自动压缩并创建「续接子会话」**(内置 `publish_compression_child`，原子结束父会话+生成子会话，Desktop 自动切到子会话)
- 压缩摘要作为 `[CONTEXT COMPACTION — REFERENCE ONLY]` 握手**直接注入子会话上下文**——续跑靠它，不是靠重读 Obsidian
- **Obsidian 记录**由 `compression-diary-watch` 补一条 `mem log`，让新会话 `mem context` 能读到「哪个会话压缩续接到哪个新会话」+ 世界可见/跨工具

## 链路五环节 + 每环节所在地(2026-09-02 实测核实)

| # | 环节 | 实现 | 状态 |
|---|------|------|------|
| 1 | 压缩引擎启用 | `config.yaml:157` `compression.enabled: true`, threshold 0.35, tail_mode lean, cloud qwen3.7-plus, timeout 600 | ✅ 启用 |
| 2 | 达阈值自动压缩 | 内置 `publish_compression_child`(自动结束父+建子会话) | ✅ 累计179次; 08-29链连压7跳 |
| 3 | 记录到 Obsidian | cron `ff8b58fe6fb2` `compression-diary-watch.py`(每3分钟) | ✅ 工作; 08-31:59写ca2a0d续接 |
| 4 | 新会话读 Obsidian | 插件 `~/.hermes/plugins/shared-work-diary/__init__.py` `pre_llm_call`→`mem context` | ✅ 本会话顶部即有注入块 |
| 5 | 任务继续 | 压缩摘要注入子会话上下文 | ✅ 链上有实测

## 关键路径速查

| 组件 | 路径 / ID |
|------|----------|
| compression 配置 | `~/.hermes/config.yaml` `compression:` 段(157行) |
| 压缩 aux 模型 | `~/.hermes/config.yaml` `auxiliary.compression` (alibaba/qwen3.7-plus/dashscope, timeout 600) |
| 续接日记 watcher 脚本 | `~/.hermes/scripts/compression-diary-watch.py` |
| watcher cron | `compression-diary-watch` (ff8b58fe6fb2), no_agent, every 3m, deliver local |
| watcher 去重状态 | `~/.hermes/logs/compression_diary_state.json` (以父会话id为key) |
| 注入插件 | `~/.hermes/plugins/shared-work-diary/__init__.py` (pre_llm_call→mem context, MAX_CONTEXT=9000) |
| 日记文件 | `~/wiki/工作日记/YYYY-MM-DD.raw.md` (注意 `.raw.md` 后缀; mem CLI 内 DIARY=工作日记) |
| 会话库 | `~/.hermes/state.db` `sessions` 表 (`parent_session_id`, `end_reason`) |
| 主动哨兵(proactive, 当前暂停) | `会话膨胀哨兵` (a5920a208179), `~/.hermes/scripts/session_sentinel.py`, soft 25万/hard 35万 |

## 验证命令(确认链路健康)

```bash
# 1. 压缩引擎是否启用
grep -n -A6 "^compression:" ~/.hermes/config.yaml

# 2. 最近压缩事件 + 是否都生了子会话(每压必1子)
sqlite3 ~/.hermes/state.db \
  "SELECT datetime(s.ended_at,'unixepoch','localtime'), s.id, c.id \
   FROM sessions s JOIN sessions c ON c.parent_session_id=s.id \
   WHERE s.end_reason='compression' ORDER BY s.ended_at DESC LIMIT 20;"

# 3. watcher 是否真写过 Obsidian
cat ~/.hermes/logs/compression_diary_state.json   # 应含父会话id(179个)
grep "上下文压缩→续接" ~/wiki/工作日记/2026-*.raw.md

# 4. 注入是否生效(新会话顶部应出现 [Shared Obsidian Work Diary…] 块)
mem context | head -5
```

## 排障要点(踩坑记录)

- **「最近没压缩」≠ 坏了**。压缩只在会话越过 0.35×窗口(=35万 token)时触发。主模型 `deepseek-v4-flash-vision-exp` 真实窗口=1M(别被 `probe-down 256k` 误导)；近几天无压缩通常只是没会话涨够，正常。
- **压缩慢≠失效**: alibaba qwen3.7-plus 处理35万token单摘要 112-260s 是正常推理耗时。`auxiliary.compression.timeout` 必须 ≥ 真实耗时(已修 75→600)。
- **勿显式设 model.context_length**: 会被 `should_clear_context_pin()` 判定清除+警告。
- **watcher 的 dry-run 绝不能写去重状态文件**(`_save_state` 只能真实运行路径调)——否则 dry-run 把待处理会话标成已处理，真实运行认为 nothing new。
- **watcher 首跑回看窗口 72h**: 窗口外当已登记塞满，避免历史压缩全量刷日记。
- **压缩本身失败时 watcher 静默是正确行为**(无续接子会话可记)。此时要修的是压缩链路(见 `hermes-compression-ops`)，不是本 watcher。
- **每次压缩只记一次**: 以父会话 id 为 key 去重登记。
- **`mem log` 会自动加 `- HH:MM | ` 前缀**，日志消息内不要再自带时间，否则时间戳重复。

## 2026-09-02 诊断记录的注意事项

- `compression-diary-watch` 今天几度出现 `missed its scheduled time`(凌晨调度补跑, 08:02→10:21 一路 lag)。会被 re-anchor 下次，建议留意但不是阻断。
- **主动哨兵(会话膨胀哨兵 a5920a208179)自 2026-08-24 起暂停**。它和压缩链无关(压缩是内置的)，但「会话到 soft 25万 主动提醒 /new + 调增量记忆整理员」这层当前是关的。若要有 proactive 提醒需重新启用。
- 哨兵 cron 调度坑: `"30m"` 解析为只跑一次(repeat=1 停)，循环必须用 `"every 30m"`；建错后 update 不修 repeat, 需 remove 重建。

## 相关

- `session-lifecycle-governance` — 阈值驱动治理哲学/双阈值/设计(互补)
- `hermes-compression-ops` — 压缩机制源码级诊断(tail_mode/分块digest)
- `project-context-milestones` — 六字段快照+里程碑换会话

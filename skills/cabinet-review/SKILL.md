---
name: cabinet-review
description: "内阁评估——Hermes 本体任议长（有上下文、可查证），机器独立真实调用 Qwen 与 Codex 两名阁员"
version: 6.0.0
author: Hermes Agent
---

# 内阁评审 · Cabinet Review

## 席位（锁定，非用户明确要求不得变更）

| 席位 | 模型 | 厂商 | 职责 |
|------|------|------|------|
| **议长** | Hermes 主模型（当前 deepseek-v4-flash） | DeepSeek | 独立意见 + 事实核实 + 最终综合裁决 |
| **阁员** | qwen3.7-plus | 阿里 DashScope | 独立第三方视角（思考预算 2500 token，避免撞 180s 超时） |
| **阁员** | Codex CLI（ChatGPT OAuth） | OpenAI | 代码级实现与运维风险 |

**每席必须来自不同厂商**——这是内阁的意义。因此不再设 DeepSeek V4 Pro 席位：
议长已经是 DeepSeek，再加 V4 Pro 等于同厂商出两份意见，独立性是假的，且成本约为 Flash 的 3 倍。

本地 Qwen（ollama）不参与内阁。

## 机制（由 cabinet-review-guard 插件强制，模型无法绕过）

```
用户召集内阁
  ↓ pre_llm_call：机器登记本轮，告知 Hermes「你是议长」
Hermes 议长：正常使用工具查资料/核实事实 → 写出自己的独立意见
  ↓ transform_llm_output 捕获该意见
机器独立调用 Qwen + Codex（并行，同席最多重试 3 次，绝不替席）
  ↓ 验签：契约哈希 / run_id / 议题哈希 / 15 分钟时效 / 席位身份 / 成功状态
Hermes 议长综合裁决（对比表 + 最终裁决）
  ↓
机器组装最终报告并交付
```

## 硬约束

- 议长**保留全部工具**用于查证；仅 `delegate_task` 被禁（防止子代理冒充阁员）。
- 议长**不得代写阁员意见**：输出中出现阁员角色标题即判定代写，本轮 fail-closed。
- 阁员意见只来自机器验签回执，模型无法伪造。
- 任一阁员失败 → 明确报告「内阁未闭环」，绝不用替代模型、角色扮演或不完整结果冒充。
- 议题简报由机器自动拼装：用户原话 + 近 10 轮会话摘录（阁员是独立进程，没有会话上下文，
  只发一句话必然产出空洞意见——这是 2026-08-15 修复的根因）。
- 阁员输出要求「结论先行 + 依据 + 风险 + 实施建议 + 置信度」，**不设句数上限**。

## 存档

每轮完整记录（议题、简报、议长意见、阁员回执、裁决、成败原因）写入
`~/.hermes/logs/cabinet/YYYYMMDD-HHMMSS-<run_id>.json`（0600），用于事后审计
「内阁到底有没有真跑」。

## ⚠️ 铁律：每轮内阁评估必须写入工作日记（2026-08-23 用户拍板）

**无论是 Mac mini 的 Hermes 还是 MacBook 的 Hermes，只要召集内阁做了评估，评估结果必须记录到工作日记**（`work-diary`，即 `~/wiki/work-diary/YYYY-MM-DD.md`，NAS 为权威存储）。

- **记录时机**：综合裁决完成后、交付用户前，必须写日记。
- **记录内容**：议题（用户原话）、结论、三席置信度、关键风险、最终裁决要点。
- **记录格式**（追加到当日日记的 `## Hermes` 段，参考 work-diary 技能）：
  `- HH:MM | 内阁评估(<轮次>, <议题简述>): 结论=... 架构/要点... 置信度=... ref: [[cabinet-review]]`
- **Mac mini 侧**：mini 直写 NAS（`ssh nas@100.108.177.1 "cat >> /home/nas/wiki/work-diary/YYYY-MM-DD.md"`，ssh stdin 传输，勿用 scp——NAS sftp 子系统受限）。
- **MacBook 侧**：MacBook 本地 `~/wiki` 为主副本，写 `~/wiki/work-diary/YYYY-MM-DD.md` 即可（MacBook 的每小时双向 sync 会推到 NAS）。
- **同步保障**：NAS 是权威源，MacBook 每小时 `sync-wiki-to-nas.sh`（已修 `--keep-newer-files` 双向保护）自动把 NAS 更新拉回 MacBook——mini 写 NAS 的评估会自动出现在 MacBook 的 Obsidian 里。
- **验证**：写完后确认当日日记文件存在且包含议题关键词（`grep -c` 或 `tail`），不确认不算完成。

## 投递故障诊断（2026-08-16 修复 + 2026-08-22 根治，别再重蹈）

**症状**：用户召集内阁后，议长意见发出去了，但阁员报告迟迟不到——用户以为"阁员慢"或"没调用阁员"，实际是报告没投递。

**2026-08-22 根治（核心代码修复，经真实端到端验收）**：
- **症状链**：存档 receipt 正常（阁员真被调用）、stdout/UI 有报告，但 `state.db` 会话里只落议长原文、报告行缺失；`api_content=None`。
- **真正根因（两个叠加）**：
  1. `transform_llm_output` 钩子原在 `_persist_session` 之后执行——报告生成时原文早已落库（时序错误）。
  2. 修复前移后仍有一个隐蔽 bug：oneshot 路径 `conversation_history=None`，写回块 `for _target in (messages, None)` 第二次迭代 `reversed(None)` 抛 TypeError，`agent._db_flush_scan_prefix = None`（在循环之后）没执行 → flush 的 bounded scan 用旧快照 identity-skip 了写回后的消息 → DB 保留议长原文。
- **修复**：`agent/turn_finalizer.py` ①transform 钩子前移到 `_persist_session` 之前；②写回 messages/conversation_history 尾部 assistant 的 content 为渲染报告并 pop `_db_persisted` marker；③`_db_flush_scan_prefix = None` **提前到写回循环之前**执行；④`conversation_history` 可能为 None（oneshot），写回 targets 元组做防护。
- **验证**：`env -u PYTHONPATH ./venv/bin/python ~/.hermes/skills/cabinet-review/scripts/test_turn_finalizer_transform.py`（13 项断言）；真实 oneshot 跑（`hermes -z "召集内阁评估..."`）后查 `state.db`：该会话出现 `### 议长独立意见（Hermes · ...）` 开头的渲染报告行（约 4-5K 字符）即闭环。
- **坑**：插件文件 444 只读，改前 `chmod u+w`、改完恢复；CLI one-shot 的 logger/print 输出可能被进程吞掉，诊断用写文件（/tmp）最可靠；`git pull` 升级 hermes-agent 会覆盖本地修复，需重新应用。

**诊断三步（先做，别直接下"没调用"结论）**：
1. `ls -lt ~/.hermes/logs/cabinet/` — 看最新存档的 `chair_opinion` 字段是否与 `topic` 对得上。对不上 = 捕获错位。
2. `grep -E "Sending response" ~/.hermes/logs/gateway.log | tail` — 议长意见发出后如果再无 outbound，就是报告没投递。
3. 对比 `chair_synthesis.latency_seconds` 与实际等待时间 — 阁员调用+综合裁决通常 1 分钟内完成，等 9 分钟必是投递断了。

**根因**：`cabinet-review-guard/__init__.py` 的 `_transform_llm_output` 在议长用工具查资料产生的**第一次中间 LLM 输出**时就 pop 掉了 active 记录，真正的完整意见到来时已无记录可消费；session 漂移时 fallback 还会把 memory/compaction 输出误当 chair_opinion。

**修复**：`_resolve_active` 只查不 pop（返回 key+active），chair_opinion 通过前置校验（长度≥150 / 无角色标题 / 无 `_MEMORY_NOISE` 噪声）后才消费。

**坑**：守卫插件文件是 444 只读（防模型篡改），修 bug 必须先 `chmod u+w`，修完恢复 444。已留 `.bak-20260816_fixed`。

**另两个坑（2026-08-16 同日修复）**：
- TRIGGER 正则的「可以/需要」太宽泛，会把「可以看到…内阁成员」这类日常用语误判为召集。修复：去掉宽泛词，窗口 `.{0,10}`→`.{0,4}`，仅保留「召集/重召/请/让」作触发词。
- 综合裁决 prompt 要的是**席位对比表 + 一致点说明**（同一议题各成员结论/置信度/依据横向对比 + 议长点明共识与分歧），不是「方案对比表」。这是用户反复强调的「清晰易读」关键——报告没有横向对比表和一致点，用户会立刻觉得退步了。

## 议长守则

- 阁员也会错——涉及具体产品/API/价格行为时，议长必须先用一手资料核实，不要直接采信任何一席。
- 综合裁决必须明确解决分歧并说明采信/否决理由，不能把矛盾结论并列了事。

"""验证 turn_finalizer pre-persist transform 修复的独立测试（无 pytest 依赖）。

背景（2026-08-22 根治）：cabinet-review-guard 的 transform_llm_output 钩子
原在 _persist_session 之后执行——渲染报告进不了会话持久化，用户只看到
议长原文。修复：钩子前移到 persist 之前，并把报告写回 messages /
conversation_history。

用法：
  cd ~/.hermes/hermes-agent
  env -u PYTHONPATH ./venv/bin/python \
    ~/.hermes/skills/cabinet-review/scripts/test_turn_finalizer_transform.py

期望输出：✅ 全部通过（13 项）。
"""
import sys
sys.path.insert(0, "/Users/vincent/.hermes/hermes-agent")

from agent import turn_finalizer as tf

CALLS = {"transform_hook": 0, "persist": 0, "persisted_messages": None}


class Budget:
    used = 0
    max_total = 40
    remaining = 40


class Agent:
    model = "deepseek-v4-flash"
    session_id = "test-session-1"
    provider = "deepseek"
    base_url = "https://api.deepseek.com/v1"
    platform = "desktop"
    iteration_budget = Budget()
    max_iterations = 40

    def __getattr__(self, name):
        if name in ("_turn_failed_file_mutations", "request_overrides"):
            return {}
        if name in ("context_compressor", "_tool_guardrail_halt_decision",
                    "_last_turn_usage", "_response_was_previewed"):
            return None
        return 0 if name.startswith(("session_", "_skill")) else False

    def _drop_trailing_empty_response_scaffolding(self, messages):
        pass

    def _file_mutation_verifier_enabled(self):
        return False

    def _turn_completion_explainer_enabled(self):
        return False

    def _drain_pending_steer(self):
        return None

    def _save_trajectory(self, messages, summary, completed):
        pass

    def _cleanup_task_resources(self, task_id):
        pass

    def clear_interrupt(self):
        return None

    def _sync_external_memory_for_turn(self, *a, **k):
        return None

    def _persist_session(self, messages, conversation_history):
        CALLS["persist"] += 1
        CALLS["persisted_messages"] = list(messages)


# monkeypatch invoke_hook（turn_finalizer 内部 from hermes_cli.lifecycle import）
import hermes_cli.lifecycle as _lifecycle

_hook_result = ["REPORTED-CABINET-TEXT"]


def fake_invoke_hook(hook_name, **kwargs):
    if hook_name == "transform_llm_output":
        CALLS["transform_hook"] += 1
        return _hook_result
    return []


_lifecycle.invoke_hook = fake_invoke_hook


def build_messages():
    return [
        {"role": "user", "content": "召集内阁"},
        {"role": "assistant", "content": "中间工具分析...",
         "tool_calls": [{"id": "c1", "type": "function",
                         "function": {"name": "terminal", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "output"},
        {"role": "assistant", "content": "【议长意见】原始文本……"},
    ]


failures = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL") + f" | {name}"
          + (f" | {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def run(interrupted=False, final="【议长意见】原始文本……"):
    CALLS.update(transform_hook=0, persist=0)
    messages = build_messages()
    conv_hist = [dict(m) for m in messages]
    result = tf.finalize_turn(
        Agent(), final_response=final, api_call_count=1,
        interrupted=interrupted, failed=False, messages=messages,
        conversation_history=conv_hist, effective_task_id="t1", turn_id="t1",
        user_message="x", original_user_message="x",
        _should_review_memory=False, _turn_exit_reason="text_response(stop)",
        _pending_verification_response=None,
        _pending_verification_response_previewed=False,
    )
    return result, messages, conv_hist


# ── 场景 1：transform 返回报告 → 写回 messages + result 标志 ──
_hook_result = ["REPORTED-CABINET-TEXT"]
result, messages, conv_hist = run()
check("1a transform 被调用", CALLS["transform_hook"] == 1)
check("1b result.final_response = 报告",
      result.get("final_response") == "REPORTED-CABINET-TEXT")
check("1c response_transformed=True", result.get("response_transformed") is True)
check("1d pre_transform_response=原文",
      result.get("pre_transform_response") == "【议长意见】原始文本……")
last_assistant = [m for m in messages
                  if m.get("role") == "assistant" and not m.get("tool_calls")][-1]
check("1e messages 最后assistant.content=报告",
      last_assistant.get("content") == "REPORTED-CABINET-TEXT")
check("1f persist 收到写回后的 messages",
      CALLS["persist"] == 1
      and CALLS["persisted_messages"][-1]["content"] == "REPORTED-CABINET-TEXT")
check("1g conv_hist 同步写回",
      [m for m in conv_hist if m.get("role") == "assistant"
       and not m.get("tool_calls")][-1]["content"] == "REPORTED-CABINET-TEXT")

# ── 场景 2：transform 返回 None → 原样 ──
_hook_result = [None]
result, messages, conv_hist = run()
check("2a transform 被调用(仍触发)", CALLS["transform_hook"] == 1)
check("2b final_response 原样",
      result.get("final_response") == "【议长意见】原始文本……")
check("2c response_transformed=False", result.get("response_transformed") is False)
check("2d messages 未改动",
      [m for m in messages if m.get("role") == "assistant"
       and not m.get("tool_calls")][-1]["content"] == "【议长意见】原始文本……")

# ── 场景 3：interrupted → transform 不被调用 ──
_hook_result = ["SHOULD-NOT-APPEAR"]
result, messages, _ = run(interrupted=True, final="")
check("3a interrupted 时 transform 不调用", CALLS["transform_hook"] == 0)
check("3b interrupted 时 result.final_response 为空",
      result.get("final_response") == "")

print()
print("=" * 60)
if failures:
    print(f"❌ {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("✅ 全部通过")

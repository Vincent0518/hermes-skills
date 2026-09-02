#!/usr/bin/env python3
"""Run the user-appointed Cabinet members; Hermes itself chairs the review."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERMES_HOME = Path.home() / ".hermes"
CONTRACT_PATH = HERMES_HOME / "skills/cabinet-review/cabinet-contract.json"
CONTRACT_LOCK_PATH = HERMES_HOME / "skills/cabinet-review/cabinet-contract.sha256"

# Headroom above the thinking budget so the visible answer is never truncated:
# the hidden chain of thought is charged against the same completion budget.
MEMBER_MAX_TOKENS = 8000
MEMBER_THINKING_BUDGET = 2500


def _valid_seat(item: object) -> bool:
    return (
        isinstance(item, dict)
        and all(str(item.get(k) or "").strip() for k in ("seat", "provider", "model", "transport"))
        and item.get("transport") in {"openai-compatible-http", "codex-cli"}
        and (item.get("transport") == "codex-cli" or all(
            str(item.get(k) or "").strip() for k in ("endpoint", "credential_variable")
        ))
    )


def load_locked_contract() -> tuple[dict[str, object], str]:
    raw = CONTRACT_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    locked = CONTRACT_LOCK_PATH.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", locked) or digest != locked:
        raise SystemExit("cabinet contract lock mismatch; explicit user-authorized reinstall required")
    contract = json.loads(raw)
    members = contract.get("members")
    if (
        contract.get("schema_version") != 4
        or contract.get("contract_id") != "hermes-chair-appointed-members-v4"
        or contract.get("locked") is not True
        or contract.get("chair_policy") != "hermes-primary-model-is-chair-with-context-and-research"
        or contract.get("member_change_policy") != "explicit_user_instruction_only"
        or not isinstance(members, list)
        or not 1 <= len(members) <= 8
        or len({item.get("seat") for item in members if isinstance(item, dict)}) != len(members)
        or any(not _valid_seat(item) for item in members)
    ):
        raise SystemExit("invalid fixed cabinet contract")
    return contract, digest


def validate_run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{8,96}", value):
        raise argparse.ArgumentTypeError("run id must be 8-96 safe characters")
    return value


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_neutral_brief(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8").strip()
    try:
        submission = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"cabinet submission is not valid JSON: {exc}") from exc
    if not isinstance(submission, dict) or set(submission) != {"neutral_brief"}:
        raise SystemExit("cabinet submission must contain exactly neutral_brief")
    brief = str(submission.get("neutral_brief") or "").strip()
    if len(brief) < 10:
        raise SystemExit("neutral brief is missing or too short")
    return brief, raw


def http_opinion(
    *, seat: str, provider: str, model: str, url: str, api_key: str,
    prompt: str, timeout: int, system_prompt: str,
) -> dict[str, object]:
    started = time.monotonic()
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": prompt}],
        "max_tokens": MEMBER_MAX_TOKENS,
        "temperature": 0.2,
    }
    if provider.startswith("dashscope"):
        # Hybrid Qwen models bill the hidden chain of thought as completion
        # tokens. Left unbounded, qwen3.8-max spent ~150s and hit the length
        # limit mid-answer, which fails closed against the 180s seat timeout.
        # A bounded budget keeps the deliberation the Cabinet exists for while
        # landing well inside the timeout; measured ~35s end to end.
        payload["enable_thinking"] = True
        payload["thinking_budget"] = MEMBER_THINKING_BUDGET
    request = Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = str(body["choices"][0]["message"]["content"] or "").strip()
        return {
            "seat": seat, "provider": provider, "requested_model": model,
            "actual_model": body.get("model") or model, "ok": bool(content),
            "latency_seconds": round(time.monotonic() - started, 2), "content": content,
        }
    except (HTTPError, URLError, TimeoutError, KeyError, ValueError) as exc:
        return {
            "seat": seat, "provider": provider, "requested_model": model, "ok": False,
            "latency_seconds": round(time.monotonic() - started, 2),
            "error": f"{type(exc).__name__}: {exc}",
        }


def codex_seat(member: dict[str, object], prompt: str, timeout: int, run_id: str) -> dict[str, object]:
    started = time.monotonic()
    output = Path(tempfile.gettempdir()) / f"hermes-cabinet-codex-{run_id}.txt"
    output.unlink(missing_ok=True)
    command = [
        "codex", "exec", "--ephemeral", "--skip-git-repo-check",
        "--sandbox", "read-only", "--color", "never", "--output-last-message", str(output),
        "-C", "/tmp",
        (f"You are the independent appointed {member['seat']} member in a Cabinet review. "
         "Do not use tools or modify files. Evaluate from a code-level implementation and "
         "operational-risk perspective. State evidence, risks, a clear verdict, and confidence. "
         "Do not claim to represent the chair or any other member.\n\n" + prompt),
    ]
    try:
        completed = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=timeout, check=False)
        content = output.read_text(encoding="utf-8") if output.exists() else ""
        output.unlink(missing_ok=True)
        result: dict[str, object] = {
            "seat": str(member["seat"]), "provider": str(member["provider"]),
            "requested_model": str(member["model"]),
            "ok": completed.returncode == 0 and bool(content.strip()),
            "latency_seconds": round(time.monotonic() - started, 2),
            "content": content.strip(), "exit_code": completed.returncode,
        }
        if not result["ok"]:
            result["error"] = completed.stderr[-1200:]
        return result
    except (subprocess.TimeoutExpired, OSError) as exc:
        output.unlink(missing_ok=True)
        return {
            "seat": str(member["seat"]), "provider": str(member["provider"]),
            "requested_model": str(member["model"]), "ok": False,
            "latency_seconds": round(time.monotonic() - started, 2),
            "error": f"{type(exc).__name__}: {exc}",
        }


def run_with_retry(job: object, attempts: int = 3) -> dict[str, object]:
    last: dict[str, object] = {}
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        last = job()  # type: ignore[operator]
        last["attempts"] = attempt
        if last.get("ok") is True:
            if errors:
                last["prior_errors"] = errors
            return last
        errors.append(str(last.get("error") or "empty response"))
        if attempt < attempts:
            time.sleep(float(attempt))
    last["prior_errors"] = errors[:-1]
    return last


_ROLE_HEADER = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?[【\[]?\s*(?:DeepSeek|Codex(?:\s+CLI)?|Qwen)"
    r"[^】\]\n]{0,24}(?:议长|阁员|成员)[】\]]?\s*$"
)


def enforce_single_voice(result: dict[str, object]) -> dict[str, object]:
    """Reject a member response that authors sections for other Cabinet roles."""
    content = str(result.get("content") or "")
    if result.get("ok") is True and _ROLE_HEADER.search(content):
        result = dict(result)
        result["ok"] = False
        result["error"] = "role impersonation: member output contains Cabinet speaker headers"
    return result


def _seat_ok(result: object, expected: dict[str, object]) -> bool:
    return (
        isinstance(result, dict)
        and result.get("seat") == expected.get("seat")
        and result.get("provider") == expected.get("provider")
        and result.get("requested_model") == expected.get("model")
        and result.get("ok") is True
        and bool(str(result.get("content") or "").strip())
    )


def validate_report(report: dict[str, object], contract: dict[str, object], digest: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if report.get("contract_version") != contract.get("schema_version"):
        errors.append("wrong contract version")
    if report.get("contract") != contract.get("contract_id"):
        errors.append("wrong contract name")
    if report.get("contract_sha256") != digest:
        errors.append("wrong contract hash")
    if not str(report.get("primary_model") or "").strip():
        errors.append("missing Hermes primary model")
    results, members = report.get("results"), contract["members"]
    if not isinstance(results, list) or len(results) != len(members):
        return False, errors + ["result count does not match appointed-member list"]
    by_seat = {str(item.get("seat")): item for item in results if isinstance(item, dict)}
    expected = {str(item["seat"]): item for item in members}
    if set(by_seat) != set(expected):
        errors.append("seat set does not match fixed contract")
    for seat, item in expected.items():
        if not _seat_ok(by_seat.get(seat), item):
            errors.append(f"{seat}: identity, status, or content mismatch")
    return not errors, errors


def atomic_private_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-id", type=validate_run_id, required=True)
    parser.add_argument("--primary-model", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    primary_model = args.primary_model.strip()
    if not primary_model:
        raise SystemExit("primary model is empty")

    brief, submission_raw = load_neutral_brief(args.prompt_file)
    contract, digest = load_locked_contract()
    members = [dict(item) for item in contract["members"]]
    env = load_env(HERMES_HOME / ".env")
    remote = [m for m in members if m["transport"] == "openai-compatible-http"]
    missing = sorted({str(item["credential_variable"]) for item in remote
                      if not env.get(str(item["credential_variable"]))})
    if missing:
        raise SystemExit("missing required credential variable(s): " + ", ".join(missing))

    jobs: dict[str, object] = {}
    for member in members:
        seat = str(member["seat"])
        if member["transport"] == "openai-compatible-http":
            jobs[seat] = lambda member=member: enforce_single_voice(http_opinion(
                seat=str(member["seat"]), provider=str(member["provider"]), model=str(member["model"]),
                url=str(member["endpoint"]), api_key=env[str(member["credential_variable"])],
                prompt=brief, timeout=args.timeout,
                system_prompt=(f"You are the independent appointed {member['seat']} member in a Cabinet "
                               "review chaired by Hermes. Give a substantive, decision-grade opinion in "
                               "Chinese: lead with your verdict, then evidence, risks, concrete "
                               "implementation advice, and a confidence level. Be specific and actionable; "
                               "never reply with only process remarks or requests for more material. "
                               "Use short paragraphs or bullets; a comparison table is welcome when "
                               "weighing options. Output ONLY your own opinion: do not write role labels, "
                               "dialogue, or any opinion attributed to the chair or another member."),
            ))
        else:
            jobs[seat] = lambda member=member: enforce_single_voice(
                codex_seat(member, brief, args.timeout, args.run_id)
            )

    completed: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {pool.submit(run_with_retry, job): name for name, job in jobs.items()}
        for future in as_completed(futures):
            completed[futures[future]] = future.result()
    order = {str(item["seat"]): i for i, item in enumerate(members)}
    results = sorted(completed.values(), key=lambda x: order.get(str(x.get("seat")), 99))

    report: dict[str, object] = {
        "contract_version": contract["schema_version"], "contract": contract["contract_id"],
        "contract_sha256": digest, "run_id": args.run_id,
        "prompt_sha256": hashlib.sha256(submission_raw.encode("utf-8")).hexdigest(),
        "neutral_brief_sha256": hashlib.sha256(brief.encode("utf-8")).hexdigest(),
        "created_at_unix": int(time.time()), "primary_model": primary_model,
        "results": results,
    }
    report["all_ok"], report["validation_errors"] = validate_report(report, contract, digest)
    atomic_private_json(args.output, report)
    print(json.dumps({
        "all_ok": report["all_ok"], "primary_model": primary_model,
        "members": [{"seat": i.get("seat"), "model": i.get("requested_model"), "ok": i.get("ok")}
                    for i in results],
    }, ensure_ascii=False))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

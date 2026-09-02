#!/usr/bin/env python3
"""scan-secrets.py — 上传前安全门禁：检出密钥/口令/内网IP/MAC 等禁止项。

用法: scan-secrets.py <path>...
退出码: 0=干净  1=检出禁止项(打印 file:line 详情)  2=参数错

规则(用户铁律 2026-09-02): 可上传的 skill 不得含
  API KEY / 口令 / 内网·环路·Tailscale IP / MAC 地址
占位示例(含 .../xxx/example/<变量> 等记号)与 env 引用(os.environ/$VAR)不算真值。
"""
import re
import sys
from pathlib import Path

# (类别, 正则, 说明)
RULES = [
    ("API密钥", re.compile(
        r"\b(sk-[A-Za-z0-9]{16,}|sk-ant-[A-Za-z0-9_-]{10,}|rk-[A-Za-z0-9]{16,}|"
        r"pk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|"
        r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AIza[0-9A-Za-z_-]{30,}|xox[baprs]-[A-Za-z0-9-]{10,})\b"),
        "疑似 API 密钥/令牌"),
    ("私钥块", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "私钥块"),
    ("口令赋值", re.compile(
        r"(?i)\b(password|passwd|api[_-]?key|api_token|access_token|client_secret|secret)\b"
        r"\s*[=:]\s*['\"]?([A-Za-z0-9_./+\-]{8,64})"),
        "口令/密钥赋值"),
    ("内网/私有IP", re.compile(
        r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}|127\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"169\.254\.\d{1,3}\.\d{1,3}|100\.(6[4-9]|[7-9][0-9]|1[0-1][0-9])\.\d{1,3}\.\d{1,3})\b"),
        "内网/环路/Tailscale IP"),
    ("MAC地址", re.compile(r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"), "MAC 地址"),
]

# 掩码/占位示例记号 → 整行豁免（示例而非真值）
PLACEHOLDER = re.compile(
    r"\.\.\.|xxx|XXXX|[Rr]edact|\bexample\b|your[_-]?|placeholder|<[a-z_]+>"
)
# env/变量引用行 → 只豁免「口令赋值」规则（读 env 的代码不算硬编码密钥）
ENVREF = re.compile(r"os\.environ|os\.getenv|getenv|env\.get|\$\{?[A-Z_][A-Z0-9_]*|keyring|credential|secrets\.|vault|\.env\b")
SKIP_SUFFIX = (".pyc", ".bak", ".repair-candidate")
SKIP_DIRS = {"__pycache__", ".git"}


def scan_line(path: Path, lineno: int, line: str):
    hits = []
    env_like = bool(ENVREF.search(line))
    for name, rx, desc in RULES:
        if env_like and name == "口令赋值":
            continue
        if rx.search(line):
            hits.append(f"{path}:{lineno} [{name}] {desc}: {line.strip()[:140]}")
    return hits


def scan_file(path: Path):
    hits = []
    try:
        text = path.read_text(errors="replace")
    except Exception:
        return hits
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or PLACEHOLDER.search(line):
            continue
        hits += scan_line(path, i, line)
    return hits


def main():
    args = [Path(a) for a in sys.argv[1:]]
    if not args:
        print("usage: scan-secrets.py <path>...", file=sys.stderr)
        return 2
    found = []
    targets = 0
    for p in args:
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix not in SKIP_SUFFIX and not any(
                        part in SKIP_DIRS for part in f.parts):
                    targets += 1
                    found += scan_file(f)
        elif p.is_file():
            targets += 1
            found += scan_file(p)
    if found:
        print(f"SECURITY_GATE: 检出 {len(found)} 处禁止项(密钥/口令/内网IP/MAC) —— 不通过：")
        for h in found:
            print("  " + h)
        return 1
    print(f"SECURITY_GATE: 干净 (扫描 {targets} 个文件)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

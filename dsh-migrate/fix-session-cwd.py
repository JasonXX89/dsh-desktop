#!/usr/bin/env python3
"""
修正会话文件首行的 cwd 字段（zstd 压缩的 jsonl）。

原则：
  - 只改第 0 行（type=session）的 cwd —— 这是功能字段
  - 历史消息正文里的 Windows 路径原样保留（那是"当时发生了什么"的记录）
  - 逐行重写：未改动的行按原始字节回写，避免任何重新序列化
"""
from __future__ import annotations
import glob
import json
import os
import re
import subprocess
import sys

SESS = "/home/jason/.dsh/sessions"

MAP = [
    (re.compile(r"^[Cc]:[\\/]{1,2}Users[\\/]{1,2}zhang[\\/]{1,2}\.openclaw[\\/]{1,2}workspace$"),
     "/home/jason/.openclaw/workspace"),
    (re.compile(r"^[Cc]:[\\/]{1,2}Users[\\/]{1,2}zhang[\\/]{1,2}openclaw-lark-2$"),
     "/home/jason/Project/openclaw-lark-2"),
    (re.compile(r"^[Cc]:[\\/]{1,2}Users[\\/]{1,2}zhang[\\/]{1,2}powerkit$"),
     "/home/jason/Project/powerkit"),
    (re.compile(r"^[Cc]:[\\/]{1,2}Users[\\/]{1,2}zhang[\\/]{1,2}DSH_workspace$"),
     "/home/jason/DSH_workspace"),
    (re.compile(r"^[Cc]:[\\/]{1,2}Users[\\/]{1,2}zhang[\\/]{1,2}\.openclaw$"),
     "/home/jason/.openclaw"),
    (re.compile(r"^[Cc]:[\\/]{1,2}Users[\\/]{1,2}zhang[\\/]{1,2}Documents[\\/]{1,2}deepseek-harness[\\/]{1,2}default-workspace$"),
     "/home/jason/文档/deepseek-harness/default-workspace"),
]


def map_path(p: str) -> str | None:
    for rx, linux in MAP:
        if rx.match(p):
            return linux
    return None


def main() -> int:
    files = sorted(glob.glob(os.path.join(SESS, "*", "*", "session.jsonl.zstd")))
    print(f"会话文件: {len(files)} 个\n")
    changed = 0
    for f in files:
        r = subprocess.run(["zstd", "-dc", f], capture_output=True)
        if r.returncode != 0:
            print(f"  ! 解压失败 {f}: {r.stderr[:120]!r}")
            continue
        raw = r.stdout
        nl = raw.find(b"\n")
        first, rest = (raw[:nl], raw[nl:]) if nl != -1 else (raw, b"")
        try:
            obj = json.loads(first.decode("utf-8"))
        except Exception as e:
            print(f"  ! 首行不可解析 {os.path.basename(os.path.dirname(f))}: {e}")
            continue
        if obj.get("type") != "session" or "cwd" not in obj:
            continue
        old = obj["cwd"]
        new = map_path(old)
        if new is None:
            print(f"  ? 未映射 cwd={old!r}  ({os.path.basename(os.path.dirname(f))})")
            continue
        if new == old:
            continue
        obj["cwd"] = new
        newfirst = json.dumps(obj, ensure_ascii=False, separators=(", ", ": ")).encode("utf-8")
        # 用 zstd 重新压缩整个文件（保持单一帧，与源一致）
        c = subprocess.run(["zstd", "-19", "-q", "-f", "-o", f + ".tmp"],
                           input=newfirst + rest, capture_output=True)
        if c.returncode != 0:
            print(f"  ! 压缩失败 {f}: {c.stderr[:150]!r}")
            continue
        os.replace(f + ".tmp", f)
        changed += 1
        print(f"  ✓ {os.path.basename(os.path.dirname(f))[:44]:46s} {old}  ->  {new}")
    print(f"\n改写 {changed} 个会话文件的 cwd")
    return 0


if __name__ == "__main__":
    sys.exit(main())

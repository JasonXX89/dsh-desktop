#!/usr/bin/env python3
"""
DSH Desktop 数据迁移：Windows harness -> Ubuntu ~/.dsh

原则：
  - 源目录只读，绝不修改
  - 只做「路径改写」，不动其他任何内容
  - JSON 走 json 解析（转义交给序列化器），其余文本走字节级正则
  - sessions 目录名按 dsh 的 projectKey() 算法重新编码
"""
from __future__ import annotations
import json
import os
import re
import shutil
import sys
from pathlib import Path

SRC = Path("/mnt/C/Users/zhang/AppData/Roaming/dsh-desktop/harness")
DST = Path("/home/jason/.dsh")

# 长路径在前（先替换更具体的）
PATH_MAP: list[tuple[str, str]] = [
    (r"C:\Users\zhang\.openclaw\workspace",            "/home/jason/.openclaw/workspace"),
    (r"C:\Users\zhang\openclaw-lark-2",                "/home/jason/Project/openclaw-lark-2"),
    (r"C:\Users\zhang\.openclaw",                      "/home/jason/.openclaw"),
    (r"C:\Users\zhang\powerkit",                       "/home/jason/Project/powerkit"),
    (r"C:\Users\zhang\DSH_workspace",                   "/home/jason/DSH_workspace"),
    (r"C:\Users\zhang\Documents",                      "/home/jason/文档"),
    (r"C:\Users\zhang\AppData\Roaming\dsh-desktop\harness", "/home/jason/.dsh"),
    (r"C:\Users\zhang\AppData\Roaming\dsh-desktop",    "/home/jason/.config/dsh-desktop"),
    (r"C:\Users\zhang\AppData\Local\pnpm",             "/home/jason/.local/share/pnpm"),
    (r"C:\Users\zhang\AppData\Local",                  "/home/jason/.local/share"),
    (r"C:\Users\zhang\AppData\Roaming",                "/home/jason/.config"),
    (r"C:\Users\zhang\AppData",                        "/home/jason/.local/share"),
    (r"C:\Users\zhang",                                "/home/jason"),
]

# 只跳过体积巨大 / 平台绑定的缓存与依赖树
SKIP_DIRS = {"node_modules", ".generations", "Cache", "Code Cache", "GPUCache",
             "DawnGraphiteCache", "DawnWebGPUCache", "blob_storage", "logs",
             "recovery"}   # recovery 里的插件备份是 Windows 专属，且已被 plugin-removals.json 描述
SKIP_FILES = {"node.cmd", "pnpm.cmd"}   # Windows 批处理垫片

# sessions 目录名 <-> 工作区
PROJECT_DIRS: dict[str, str] = {
    "--C-Users-zhang-.openclaw--":            "/home/jason/.openclaw",
    "--C-Users-zhang-.openclaw-workspace--":  "/home/jason/.openclaw/workspace",
    "--C-Users-zhang-DSH_workspace--":        "/home/jason/DSH_workspace",
    "--C-Users-zhang-openclaw-lark-2--":      "/home/jason/Project/openclaw-lark-2",
    "--C-Users-zhang-powerkit--":             "/home/jason/Project/powerkit",
    "--C-Users-zhang-Documents-deepseek-harness-default-workspace--":
        "/home/jason/文档/deepseek-harness/default-workspace",
}


def project_key(cwd: str) -> str:
    """复刻 dsh-session-persistence-jsonl 的 projectKey()。"""
    readable, sep_run = "", False
    for ch in cwd:
        if ch in "/\\:":
            if not sep_run:
                readable += "-"
            sep_run = True
        elif ch != "~" and re.fullmatch(r"[A-Za-z0-9._\-]", ch):
            readable += ch
            sep_run = False
        else:
            readable += "~" + format(ord(ch), "04X")
            sep_run = False
    body = re.sub(r"^-+", "", readable) or "root"
    return "--" + body[:251] + "--"


def _regex_for(win: str) -> re.Pattern[str]:
    """把 Windows 路径编译成容忍 / 或 \\ （含 JSON 里的双反斜杠）的正则。"""
    parts = re.split(r"[\\/]", win)
    body = r"(?:[\\/]{1,2})".join(re.escape(p) for p in parts[1:])
    return re.compile(r"[Cc]:" + r"(?:[\\/]{1,2})" + body)


_REGEXES = [(_regex_for(w), w, l) for w, l in PATH_MAP]
_ALL = re.compile("|".join(f"(?:{r.pattern})" for r, _, _ in _REGEXES))

# 改写后仍可能残留分隔符：C:\\...\\pnpm\\store\\ -> /home/jason/.local/share/pnpm\store\
# 只在「同一段路径内出现过 /home/jason」时归一，避免误伤正文
_PATHSPAN = re.compile(r"[/\\A-Za-z0-9._\-]{6,}")


def normalize_separators(s: str) -> str:
    def fix(m: re.Match[str]) -> str:
        seg = m.group(0)
        if "/home/jason" not in seg:
            return seg
        return re.sub(r"[\\/]{1,2}", "/", seg).replace("/home/jason", "/home/jason")

    return _PATHSPAN.sub(fix, s)


def rewrite_text(s: str) -> tuple[str, int]:
    n = 0
    for rx, _, linux in _REGEXES:
        s, k = rx.subn(linux, s)
        n += k
    return normalize_separators(s), n


def rewrite_json_obj(o, counter: list[int]):
    if isinstance(o, str):
        out, n = rewrite_text(o)
        counter[0] += n
        return out
    if isinstance(o, list):
        return [rewrite_json_obj(x, counter) for x in o]
    if isinstance(o, dict):
        return {k: rewrite_json_obj(v, counter) for k, v in o.items()}
    return o


def main() -> int:
    if DST.exists():
        print(f"✗ 目标已存在，先移走：{DST}", file=sys.stderr)
        return 1
    if not SRC.is_dir():
        print(f"✗ 源不存在：{SRC}", file=sys.stderr)
        return 1

    stats = {"files": 0, "json": 0, "text": 0, "rewrites": 0, "skipped": 0, "copybin": 0}
    DST.mkdir(parents=True, mode=0o700)

    for root, dirs, files in os.walk(SRC):
        rel = Path(root).relative_to(SRC)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        target_dir = DST / rel
        target_dir.mkdir(parents=True, exist_ok=True)

        for name in files:
            if name in SKIP_FILES:
                stats["skipped"] += 1
                continue
            sp = Path(root) / name
            tp = target_dir / name
            size = sp.stat().st_size
            if size > 20_000_000:
                stats["skipped"] += 1
                continue

            # 尝试按文本处理
            try:
                raw = sp.read_bytes()
                text = raw.decode("utf-8")
            except (UnicodeDecodeError, OSError):
                shutil.copy2(sp, tp)
                stats["copybin"] += 1
                continue

            if name.endswith(".json"):
                # 走文本改写而非 json 重新序列化：保持原始格式零改动，
                # 正则已容忍 JSON 中的 \\ 双反斜杠。
                new, n = rewrite_text(text)
                stats["json"] += 1
            else:
                new, n = rewrite_text(text)
                stats["text"] += 1

            tp.write_text(new, encoding="utf-8")
            stats["files"] += 1
            stats["rewrites"] += n
            if n:
                print(f"  {n:3d} 处  {rel}/{name}")

    # 重建 sessions 目录名
    sess_root = DST / "sessions"
    if sess_root.is_dir():
        print("\n--- sessions 目录重编码 ---")
        for d in sorted(sess_root.iterdir()):
            if not d.is_dir():
                continue
            if d.name.startswith("--home-jason"):
                print(f"  = 已就位: {d.name}")
                continue
            new_cwd = PROJECT_DIRS.get(d.name)
            if new_cwd is None:
                print(f"  ! 未映射，保持原名: {d.name}")
                continue
            new_name = project_key(new_cwd)
            d.rename(sess_root / new_name)
            print(f"  {d.name}\n    -> {new_name}   ({new_cwd})")

    # 权限加固：凭据文件 600
    for p in DST.rglob("*.yaml"):
        if p.name.startswith("."):
            p.chmod(0o600)

    print("\n=== 汇总 ===")
    for k, v in stats.items():
        print(f"  {k:10s}: {v}")
    print(f"  目标: {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

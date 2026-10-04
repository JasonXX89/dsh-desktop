#!/usr/bin/env python3
"""探明 Win Desktop 内置 dsh 版本 + 会话文件 schema。"""
import json
import os
import struct
import sys

ASAR = "/mnt/D/Programs/DeepSeek Harness/resources/app.asar"


def asar_header(path: str) -> dict:
    with open(path, "rb") as f:
        b = f.read(16)
        a, pickle_size, str_plus4, str_size = struct.unpack("<IIII", b)
        raw = f.read(str_size)
    return json.loads(raw.decode("utf-8"))


def tree_walk(node, path="", want=()):
    for name, v in node.get("files", {}).items():
        np = f"{path}/{name}"
        if "files" in v:
            yield from tree_walk(v, np, want)
        else:
            if any(np.endswith(w) for w in want):
                yield np, v


def main() -> int:
    print("=" * 62)
    print("① app.asar 头解析")
    hdr = asar_header(ASAR)
    top = list(hdr.get("files", {}).keys())
    print("  顶层:", top[:15])

    print("\n② asar 内查找 dsh 的 package.json / 版本元数据")
    hits = list(tree_walk(hdr, "", ("@deepseek-ai/dsh/package.json",
                                    "desktop-runtime.json",
                                    "app/package.json",
                                    "package.json")))
    for np, v in hits[:25]:
        if np.count("/") <= 3 or "desktop-runtime" in np or "dsh/package.json" in np:
            print(f"  {v.get('size',0):>10}  {np}")

    print("\n③ 猜测的 dsh 目录层级")
    node = hdr.get("files", {})
    for k in ("app", "dsh", "node_modules"):
        if k in node and "files" in node[k]:
            print(f"  /{k}/ -> {list(node[k]['files'])[:12]}")

    print("\n" + "=" * 62)
    print("④ 本机 dsh 的关键子包版本（对照 peerDep）")
    base = os.path.expanduser("~/.npm-global/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai")
    for pkg in ("dsh-settings", "dsh-base", "dsh-web-app"):
        p = os.path.join(base, pkg, "package.json")
        try:
            d = json.load(open(p))
            print(f"  {pkg:16s} {d.get('version')}")
        except Exception as e:
            print(f"  {pkg:16s} ERR {e}")

    print("\n⑤ dshmarket@1.39.0 的完整 peerDependencies")
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://registry.npmjs.org/dshmarket/1.39.0",
            headers={"User-Agent": "curl/8"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        print("  peerDependencies:", json.dumps(d.get("peerDependencies", {}), indent=4))
        print("  engines:", d.get("engines"))
    except Exception as e:
        print("  拉取失败:", e)

    return 0


if __name__ == "__main__":
    sys.exit(main())

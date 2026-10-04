#!/usr/bin/env python3
"""
把 settings.yaml.imported 里的 llm-pi-ai.providers 落到 profile 补丁层。

背景：dsh-settings 的 legacy 导入会把 settings.yaml 拆到各命名空间，
但 llm-pi-ai 声明了 settings.configure({auto:false})，命名空间未注册，
导入被拒（其余三节 ui-onboarding / agent-default-model / ui-theme 已成功）。

profile 补丁层（cordis.patch.yml）是官方支持的 id 定向配置覆盖通道，
与 Windows 上 settings.yaml 被组合进同一棵配置树的效果等价。
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

import yaml

IMPORTED = Path("/home/jason/.dsh/settings.yaml.imported")
PATCH = Path("/home/jason/.dsh/profiles/web/cordis.patch.yml")
HIERARCHY = "!!js"          # 保留 dsh 的 JS 标签语义用的占位（此处不用）


def main() -> int:
    src = yaml.safe_load(IMPORTED.read_text(encoding="utf-8"))
    providers = (src.get("llm-pi-ai") or {}).get("providers")
    if not providers:
        print("✗ 源里没有 llm-pi-ai.providers")
        return 1

    shutil.copy2(PATCH, PATCH.with_suffix(".yml.bak"))
    entries = yaml.safe_load(PATCH.read_text(encoding="utf-8")) or []

    # 移除已存在的同名条目，再追加
    entries = [e for e in entries if e.get("id") != "llm-pi-ai"]
    entries.append({
        "id": "llm-pi-ai",
        "name": "@deepseek-ai/dsh-llm-pi-ai",
        "config": {"providers": providers},
    })

    PATCH.write_text(
        "# Your patch layer for this dsh profile, applied after every bundle layer:\n"
        "# a top-level YAML array of loader patch entries (id-targeted config\n"
        "# overrides, disables, and insert lists; `!!js` expressions allowed).\n"
        + yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )

    print(f"✓ 写入 {PATCH}")
    print(f"  备份 {PATCH.with_suffix('.yml.bak')}")
    for pid, prof in providers.items():
        api = prof.get("api", "(用默认)")
        models = len(prof.get("models") or [])
        print(f"  provider {pid}: api={api} baseURL={prof.get('baseURL','-')} "
              f"apiKeyEnv={prof.get('apiKeyEnv','-')} models={models}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

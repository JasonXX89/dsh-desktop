# DeepSeek Harness — Ubuntu 端项目

把 Windows 上的 **DeepSeek Harness Desktop** 迁移到 Ubuntu 的完整工作区，
并提供一个**独立应用窗口**启动器（不依赖官方尚未发布的 Linux 桌面壳）。

## 目录结构

| 路径 | 内容 |
|---|---|
| `dsh-src/` | 上游 `deepseek-ai/deepseek-harness` 源码（sparse + partial clone，仅 `apps/desktop` + `scripts` + 索引） |
| `dsh-migrate/` | 迁移脚本 + 会话备份 |
| `bin/dsh-app` | 启动器：拉服务 → 抓 token → 开独立窗口 → 守生命周期 |
| `icons/` | 应用图标 8 档尺寸（16→512，源自上游 `icon.png`） |

## 快速使用

```bash
dsh-app            # 等价于 ~/.local/bin/dsh-app（软链）
```

行为：**即点即用，关窗即停**。

1. 点图标/命令 → 后台拉起 `dsh web`（子进程）
2. 取输出里的一次性 token → 拼带鉴权的 URL
3. 用 Edge `--app=` 模式开独立窗口（无地址栏、独立任务栏项）
4. 关窗 → 脚本感知 → 停服务 → 自己退出，**不留后台进程**

## 关键设计（踩坑换来的）

### 1. Wayland 下 app_id 的控制

**Chromium 在 Wayland 原生模式无视 `--class`**，自己按
`msedge-<URL主机>__-<--profile-directory>` 造 app_id。
用 `WAYLAND_DEBUG=1` 可读协议层真值（`set_app_id`）。

实测四种组合：

| 参数 | 实际 `set_app_id` |
|---|---|
| 无 `--class` | `msedge-127.0.0.1__-Default` |
| `--class=dsh-desktop` | `msedge-127.0.0.1__-Default` ← 无效 |
| `--profile-directory=DeepSeekHarness` | `msedge-127.0.0.1__-DeepSeekHarness` |
| `--profile-directory=dsh` + URL 用 `localhost` | **`msedge-localhost__-dsh`** |

两个关键点：
- **必须用 `localhost` 而非 `127.0.0.1`** —— 点号让 app_id 成为非法 D-Bus 名，GNOME 会加前导 `-`，破坏匹配。
- **desktop 文件名必须等于推导出的 app_id**（GNOME 靠 basename 精确匹配关联图标/名称/蓝点）。
  `~/.local/share/applications/msedge-localhost__-dsh.desktop`

### 2. dsh 数据迁移的坑

- **版本必须对齐**：源 Desktop 捆绑 `@deepseek-ai/dsh-desktop-runtime 0.1.7-rc.1`
  → 本机装 `@deepseek-ai/dsh@0.1.7-rc.1`，否则插件 peerDep 不满足。
  安装必须带 `--allow-scripts`（koffi / node-pty 的原生二进制）。
- **`settings.yaml` 会被改名 `.imported`** —— 是设计（legacy 导入），不是损坏。
  但声明 `settings.configure({auto:false})` 的插件（`llm-pi-ai`）那节**会被拒、丢失**，
  需手工补进 `~/.dsh/profiles/web/cordis.patch.yml`。
- **会话目录名有编码算法**：见 `@deepseek-ai/dsh-session-persistence-jsonl` 的 `projectKey()`
  （非 `[A-Za-z0-9._-]` → `~` + 4 位大写 hex；分隔符压缩为单个 `-`；首尾 `--`）。
- 会话文件是 zstd 压缩的 jsonl，首行含 `cwd`；**只改首行 cwd**，历史正文保持原样。

## 迁移脚本

| 脚本 | 作用 |
|---|---|
| `import-dsh-home.py` | 复制 `%APPDATA%\dsh-desktop\harness` → `~/.dsh`，改写 Windows 路径 |
| `fix-session-cwd.py` | 改写会话首行 `cwd`（不动历史正文） |
| `apply-providers.py` | 把被拒的 `llm-pi-ai.providers` 补进 profile 补丁层 |
| `probe-desktop.py` | 解析 Win 安装包的 asar 头，读出内置 dsh 版本 |

## 待办 / 已知限制

- **无官方 Linux 桌面壳**：上游 `apps/desktop` 只发布 `mac-arm64/mac-x64/win-x64`。
  自建 Linux AppImage 受限于源码树下载速度（本机 ~3–6 KB/s），暂搁置。
- **Dock 悬停名**：由 app_id 尾缀决定（显示 "Dsh"）。要显示全名需改页面的
  Web App Manifest（`<link rel=manifest>`）。
- `dsh-migrate/sessions.bak-*/` 是 **4.8 MB 的完整对话历史**，仅因本库为私有才纳入。

## 环境依赖

- `dsh` 全局安装（`~/.npm-global/bin/dsh`）
- `microsoft-edge` 或其它 Chromium 系浏览器
- Python 3 + Pillow（仅图标重生成用）

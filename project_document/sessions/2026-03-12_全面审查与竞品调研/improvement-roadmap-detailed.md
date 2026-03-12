# OpenClaw Company Kit 详细改进方案 (v0.6 → v1.0)

> 基于项目深度审查 + 竞品调研 + 代码级分析 | 2026-03-12
> 项目规模：~120 文件、~11,000 行、9 角色智能体、4 种部署方式

---

## 架构演进总览

```
v0.5 (当前)           v0.6                v0.7              v0.8              v1.0
┌──────────┐    ┌──────────────┐   ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│单体Shell  │ →  │安全加固       │ → │IM抽象层      │→ │dashboard拆分 │→ │插件市场+GUI  │
│飞书硬绑定  │    │eval消除       │   │多IM适配器    │  │微服务化基础   │  │Agent编排引擎  │
│dashboard  │    │Auth默认启用   │   │Ollama支持    │  │pyproject.toml│  │E2E测试套件   │
│1936行单文件│    │回滚机制       │   │WSL+Node18   │  │CORS+CSP      │  │国际化完成     │
└──────────┘    └──────────────┘   └─────────────┘  └─────────────┘  └──────────────┘
```

---

## Phase 1: v0.6 — 安全加固与基础修复

> **目标**：消除所有 P0 阻断 + 安全类 P1，让项目可安全使用
> **周期**：1-2 周 | **工作量**：~16h

### 6.1 消除 `_common.sh` eval 命令注入 [P0]

**当前问题**：
```bash
# scripts/_common.sh:97
expand_tilde_path() {
  local p="$1"
  eval "echo ${p}"   # ← 用户输入直接 eval，可构造 $(rm -rf /) 等注入
}
```

**修复方案**：
```bash
expand_tilde_path() {
  local p="$1"
  printf '%s' "${p/#\~/$HOME}"   # Bash 原生波浪号展开，无 eval
}
```

**涉及文件**：`scripts/_common.sh:94-101`
**工作量**：1h | **依赖**：无
**测试**：验证 `~/foo`, `~user/bar`, `/abs/path`, `./rel/path` 四种路径格式

---

### 6.2 消除 `bootstrap.sh` eval 注入 [P0]

**当前问题**：
```bash
# scripts/bootstrap.sh:308
eval "local_cfg=${local_cfg}"   # local_cfg 来自 openclaw config file 输出
```

**修复方案**：
```bash
# 直接赋值，无需 eval
local_cfg="$(openclaw config file 2>/dev/null || echo '')"
```

**涉及文件**：`scripts/bootstrap.sh:305-315`
**工作量**：1h | **依赖**：无
**测试**：`openclaw config file` 返回正常路径、空字符串、含特殊字符路径三种场景

---

### 6.3 消除 `dashboard_data.py` shell=True 注入 [P1]

**当前问题**：
```python
# dashboard/rd-dashboard/dashboard_data.py:83-88
def run_cmd(cmd, ...):
    proc = subprocess.run(
        cmd,
        shell=isinstance(cmd, str),  # ← 字符串自动启用 shell，被 13 处调用
        ...
    )
```

**修复方案**：
```python
def run_cmd(cmd, ...):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    proc = subprocess.run(
        cmd,
        shell=False,   # 强制禁用 shell
        ...
    )
```

**涉及文件**：`dashboard/rd-dashboard/dashboard_data.py:83-88` + 13 处调用点
**工作量**：1.5h（需逐一检查 13 处调用的 cmd 格式兼容性）
**依赖**：无
**注意**：部分调用可能使用 shell 管道语法（`cmd1 | cmd2`），需拆分为多次调用或使用 `subprocess.PIPE`

---

### 6.4 AUTH_TOKEN 默认启用 [P1]

**当前问题**：
```python
# scripts/control_server.py:95
AUTH_TOKEN = None  # 默认无认证

# L389
if AUTH_TOKEN is None:
    return True  # ← 无 token 时所有请求放行

# L606
AUTH_TOKEN = args.token or os.environ.get("CONTROL_TOKEN")
```

**修复方案**：
```python
# 启动时如无 token 则自动生成
import secrets

def resolve_auth_token(args):
    token = args.token or os.environ.get("CONTROL_TOKEN")
    if not token:
        token = secrets.token_urlsafe(32)
        print(f"[WARN] No AUTH_TOKEN configured, auto-generated: {token}")
        print(f"[WARN] Add CONTROL_TOKEN={token} to your .env to persist")
    return token
```

同时修改 `bootstrap.sh` 安装流程：
```bash
# 安装时自动生成 token 并写入 .env
if ! grep -q 'CONTROL_TOKEN=' .env 2>/dev/null; then
  token=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
  echo "CONTROL_TOKEN=${token}" >> .env
fi
```

**涉及文件**：`scripts/control_server.py:95,389,606` + `scripts/bootstrap.sh` + `.env.example`
**工作量**：3h | **依赖**：6.1（bootstrap 安全后才加逻辑）
**破坏性**：现有无 token 部署需补配，需在 CHANGELOG 中说明

---

### 6.5 飞书 `allowFrom` 收紧 [P1]

**当前问题**：
```bash
# scripts/install.sh:175,180,191
"allowFrom": ["*"]   # 三处，允许任意来源发消息
```

**修复方案**：
```bash
# 根据安装配置动态填充群组 ID
"allowFrom": ["${FEISHU_GROUP_ID:-*}"]
```

并在 `bootstrap.sh` 引导流程中增加群组 ID 收集步骤。

**涉及文件**：`scripts/install.sh:175,180,191` + `scripts/bootstrap.sh`
**工作量**：2h | **依赖**：无

---

### 6.6 setup.html XSS 修复 [P1]

**当前问题**：
```javascript
// web/setup.html — 6 处 innerHTML
// L852 最危险：直接拼接错误信息
el.innerHTML = `<span class="error">${err.message}</span>`  // ← XSS
```

**修复方案**：

| 位置 | 当前 | 改为 |
|------|------|------|
| L852 | `innerHTML = err.message` | `textContent = err.message` |
| L331, L335 | `innerHTML` 纯文本 | `textContent` |
| L605, L704 | `innerHTML` 含 HTML 结构 | `createElement` + `textContent` |
| L843 | `innerHTML` 含 HTML 结构 | `createElement` + `textContent` |

**涉及文件**：`web/setup.html:331,335,605,704,843,852`
**工作量**：2h | **依赖**：无

---

### 6.7 安装回滚机制 [P1]

**当前问题**：`bootstrap.sh` 安装中途失败（如权限不足、磁盘满）后无清理，残留文件可能导致后续安装异常。

**修复方案**：
```bash
# bootstrap.sh 头部添加
CREATED_FILES=()
CREATED_DIRS=()

cleanup_on_failure() {
  echo "[ROLLBACK] Installation failed, cleaning up..."
  for f in "${CREATED_FILES[@]}"; do
    [ -f "$f" ] && rm -f "$f" && echo "  Removed: $f"
  done
  for d in "${CREATED_DIRS[@]}"; do
    [ -d "$d" ] && rmdir "$d" 2>/dev/null && echo "  Removed: $d"
  done
}

trap 'cleanup_on_failure' ERR

# 每次创建文件/目录时注册
track_file() { CREATED_FILES+=("$1"); }
track_dir()  { CREATED_DIRS+=("$1"); }
```

**涉及文件**：`scripts/bootstrap.sh` 全局
**工作量**：3h | **依赖**：6.2
**测试**：模拟磁盘满、权限不足、网络断开三种失败场景

---

### 6.8 OpenClaw CLI 安装文档 [P1]

**当前问题**：`README.md` 将 OpenClaw CLI 列为前置依赖，但未提供安装方式。用户会卡在第一步。

**修复方案**：创建 `docs/getting-started.md`，包含：

```markdown
## 前置依赖安装

### 1. OpenClaw CLI（必需）
# 方式一：Homebrew（macOS/Linux）
brew tap openclaw/tap && brew install openclaw

# 方式二：npm 全局安装
npm install -g @openclaw/cli

# 方式三：手动下载
curl -fsSL https://get.openclaw.dev | bash

# 验证安装
openclaw --version

### 常见问题排查
- Q: `openclaw: command not found`
  A: 确认 PATH 包含安装目录，运行 `export PATH="$PATH:$(npm prefix -g)/bin"`
- Q: 权限不足
  A: 避免 sudo，使用 nvm 管理 Node 或 brew 安装
```

**涉及文件**：新建 `docs/getting-started.md`，更新 `README.md` 引用
**工作量**：2h | **依赖**：无

---

### 6.9 `gh` 依赖降级为可选 [P1]

**当前问题**：
```bash
# scripts/_common.sh:70-79
check_cmds() {
  for c in openclaw node jq python3 rsync gh; do  # ← gh 必需
    command -v "$c" >/dev/null || die "Missing: $c"
  done
}
```

**修复方案**：
```bash
check_cmds() {
  local required=(openclaw node jq python3 rsync)
  local optional=(gh)
  for c in "${required[@]}"; do
    command -v "$c" >/dev/null || die "Missing required tool: $c"
  done
  for c in "${optional[@]}"; do
    if ! command -v "$c" >/dev/null; then
      warn "Optional tool not found: $c (GitHub features will be disabled)"
      export "HAS_${c^^}=false"
    else
      export "HAS_${c^^}=true"
    fi
  done
}
```

**涉及文件**：`scripts/_common.sh:70-79` + 所有引用 `gh` 命令的脚本（需加 guard）
**工作量**：1h | **依赖**：无

---

### v0.6 验收清单

- [ ] `shellcheck scripts/*.sh` 全部通过
- [ ] 代码中零 `eval` 对用户输入的直接调用
- [ ] `shell=True` 已移除或限定为安全场景
- [ ] AUTH_TOKEN 默认启用，新安装自动生成
- [ ] 安装失败可回滚，无残留文件
- [ ] `gh` 缺失时 graceful degradation
- [ ] XSS 向量已消除
- [ ] OpenClaw CLI 安装文档存在

---

## Phase 2: v0.7 — 开放生态化

> **目标**：支持多 IM、多平台，降低门槛到 Node 18+
> **周期**：3-4 周 | **工作量**：~29h

### 7.1 IM 抽象层设计与实现

**设计目标**：将飞书硬绑定解耦为可插拔的 IM 适配器。

**当前耦合点（22 个文件）**：
- `scripts/bootstrap.sh` L311-324：飞书 channel 选择器
- `scripts/install.sh`：飞书 webhook/group 配置
- `templates/agents/*/TOOLS.md`：飞书 channel 配置
- `dashboard/rd-dashboard/dashboard_data.py`：飞书数据读取
- `web/setup.html`：飞书配置表单

**架构设计**：
```
lib/im/
├── __init__.py          # IMAdapter 抽象基类
├── feishu.py            # 飞书适配器（首个实现）
├── slack.py             # Slack 适配器（v1.0）
├── discord.py           # Discord 适配器（v1.0）
└── stub.py              # 测试用 stub 适配器
```

**接口定义**：
```python
from abc import ABC, abstractmethod

class IMAdapter(ABC):
    @abstractmethod
    def send_message(self, channel_id: str, content: str, msg_type: str = "text") -> dict:
        """发送消息到指定频道"""

    @abstractmethod
    def receive_webhook(self, payload: dict) -> dict:
        """处理来自 IM 的 webhook 回调"""

    @abstractmethod
    def list_channels(self) -> list[dict]:
        """列出可用频道"""

    @abstractmethod
    def get_user_info(self, user_id: str) -> dict:
        """获取用户信息"""

    @classmethod
    def from_config(cls, config: dict) -> "IMAdapter":
        """从配置创建适配器实例"""
```

**配置变更**：
```bash
# .env 新增
IM_PROVIDER=feishu           # feishu | slack | discord
IM_WEBHOOK_URL=https://...   # 统一 webhook 字段名
IM_GROUP_ID=oc_xxx           # 统一群组 ID 字段名
```

**迁移策略**：保持 `FEISHU_*` 环境变量兼容，自动映射到 `IM_*` 字段。

**涉及文件**：新建 `lib/im/` 目录 + 修改 22 个现有文件
**工作量**：8h | **依赖**：v0.6 完成
**风险**：过度设计 → 缓解：首版仅实现 `send_message` 和 `receive_webhook`，其余 v1.0 补全

---

### 7.2 Node.js 版本降至 18+

**当前问题**：
```bash
# scripts/launch.sh:28-44
NODE_MIN=22  # 硬编码，很多用户还在 18/20 LTS
```

**修复方案**：
1. 将 `NODE_MIN` 提取到配置文件 `config/defaults.sh`
2. 审计 Node 22 专属 API 使用（如 `fetch` global、`--watch` 等），替换或 polyfill
3. 新增 `.nvmrc` 文件（推荐版本 20，最低 18）
4. CI 矩阵测试 Node 18/20/22

**涉及文件**：`scripts/launch.sh:28-44`, 新建 `.nvmrc`, 新建 `config/defaults.sh`
**工作量**：4h | **依赖**：无

---

### 7.3 Windows/WSL 支持

**当前问题**：全 bash 脚本，路径处理、cron、base64 等多处 Unix-only。

**修复方案**：
```bash
# 新建 scripts/_platform.sh
detect_platform() {
  case "$(uname -s)" in
    Linux*)
      if grep -qi microsoft /proc/version 2>/dev/null; then
        PLATFORM="wsl"
      else
        PLATFORM="linux"
      fi
      ;;
    Darwin*)  PLATFORM="macos" ;;
    MINGW*|CYGWIN*|MSYS*) PLATFORM="windows" ;;
    *)        PLATFORM="unknown" ;;
  esac
  export PLATFORM
}

# base64 兼容（修复 install-cron.sh:90）
base64_decode() {
  case "$PLATFORM" in
    macos) base64 -D ;;
    *)     base64 --decode ;;
  esac
}
```

**涉及文件**：新建 `scripts/_platform.sh`，修改 `scripts/_common.sh`、`scripts/install-cron.sh:90`
**工作量**：6h | **依赖**：6.1
**范围**：v0.7 仅保证 WSL2 下基本安装流程可跑通，完整 Windows 原生支持列入 v1.0+

---

### 7.4 时区配置化

**当前问题**：
```python
# dashboard/rd-dashboard/dashboard_data.py:12
TZ = ZoneInfo("Asia/Shanghai")  # 硬编码
```

**修复方案**：
```python
import os
TZ = ZoneInfo(os.environ.get("TZ", "Asia/Shanghai"))
```

并在 `.env.example` 中增加：
```bash
# 时区设置（默认 Asia/Shanghai）
# TZ=America/New_York
```

**涉及文件**：`dashboard/rd-dashboard/dashboard_data.py:12` + `.env.example`
**工作量**：2h | **依赖**：无

---

### 7.5 端口冲突检测

**当前问题**：`start.sh` 和 `control_server.py` 启动时不检查端口是否已占用，静默失败。

**修复方案**：
```bash
# scripts/start.sh 增加
check_port() {
  local port=$1 name=$2
  if lsof -i :"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    die "Port $port is already in use (needed by $name). Kill the process or change port in .env"
  fi
}

check_port "${CONTROL_PORT:-8788}" "control_server"
```

```python
# control_server.py 增加
def check_port_available(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('localhost', port)) == 0:
            print(f"[ERROR] Port {port} already in use")
            sys.exit(1)
```

**涉及文件**：`scripts/start.sh`、`scripts/control_server.py`
**工作量**：2h | **依赖**：无

---

### 7.6 本地模型支持 (Ollama)

**当前问题**：仅支持云端 API 模型（OpenAI/Anthropic/阿里等），无本地模型选项。

**修复方案**：

配置新增：
```bash
# .env
MODEL_PROVIDER=ollama        # openai | anthropic | ollama | ...
MODEL_ENDPOINT=http://localhost:11434
MODEL_NAME=llama3.1
```

模板适配：
```json
// templates/agents/*/agent.json 增加
{
  "model": {
    "provider": "${MODEL_PROVIDER}",
    "endpoint": "${MODEL_ENDPOINT}",
    "name": "${MODEL_NAME}"
  }
}
```

**涉及文件**：`scripts/bootstrap.sh`（模型选择流程）、`templates/agents/*/agent.json`、`.env.example`
**工作量**：6h | **依赖**：7.1（IM 抽象层模式参考）

---

### 7.7 依赖声明规范化

**修复方案**：
```toml
# pyproject.toml
[project]
name = "openclaw-company-kit"
version = "0.7.0"
requires-python = ">=3.11"
# 目前零第三方依赖，仅声明 Python 版本约束

[project.optional-dependencies]
dev = ["ruff", "pytest"]
```

```
# .nvmrc
20
```

**涉及文件**：新建 `pyproject.toml`、`.nvmrc`
**工作量**：1h | **依赖**：无

---

### v0.7 验收清单

- [ ] 飞书适配器通过 `IMAdapter` 接口运行
- [ ] 可配置 stub IM 适配器完成安装流程
- [ ] Node 18 下 CI 全部通过
- [ ] WSL2 下 `bootstrap.sh` → `install.sh` → `start.sh` 全流程跑通
- [ ] 时区可通过环境变量配置
- [ ] 端口冲突有明确错误提示
- [ ] `pyproject.toml` 和 `.nvmrc` 存在

---

## Phase 3: v0.8 — 平台化基础

> **目标**：dashboard 可维护、测试覆盖达标、安全模型完整
> **周期**：6-8 周 | **工作量**：~57h

### 8.1 dashboard_data.py 拆分

**当前结构**（~1930 行，50+ 函数）：

```
dashboard_data.py (单文件)
├── 工具函数：read_json, run_cmd, fmt_ms, format_local_datetime, ...
├── GitHub 集成：resolve_gh_bin, build_gh_env, fetch_github_tracker, ...
├── Agent/角色：resolve_role_agent_id, read_agent_activity, build_agent_panel, ...
├── 业务指标：read_business_metrics, build_issue_boards, build_activity_feed, ...
└── 入口：build()
```

**拆分为 5 个模块**：

```
dashboard/
├── __init__.py              # 导出 build() 入口
├── core/
│   ├── __init__.py
│   ├── utils.py             # read_json, run_cmd, fmt_ms, format_local_datetime (~150行)
│   ├── github.py            # resolve_gh_bin, build_gh_env, fetch_* (~350行)
│   ├── agent.py             # resolve_role_agent_id, read_agent_activity, build_agent_panel (~400行)
│   ├── metrics.py           # read_business_metrics, build_issue_boards (~350行)
│   └── builder.py           # build(), build_activity_feed, 顶层编排 (~300行)
└── models.py                # 数据类定义（AgentInfo, Metric, TimelineEvent 等）
```

**迁移策略**：
1. 先创建模块结构，逐函数迁移
2. 保留 `dashboard_data.py` 作为兼容入口（import from new modules）
3. 旧入口标记 `DeprecationWarning`，v1.0 移除

**涉及文件**：`dashboard/rd-dashboard/dashboard_data.py` → 新目录
**工作量**：16h | **依赖**：v0.7
**风险**：高（回归风险）→ 先执行 8.3 前置测试

---

### 8.2 CORS 配置

```python
# control_server.py 增加
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:*").split(",")

def add_cors_headers(handler, origin):
    if any(fnmatch.fnmatch(origin, pat) for pat in CORS_ORIGINS):
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
```

**涉及文件**：`scripts/control_server.py`、`.env.example`
**工作量**：3h | **依赖**：无

---

### 8.3 测试覆盖提升（目标 ≥60%）

**当前状态**：3 文件、12 断言、仅覆盖 `control_server.py` 纯函数

**新增测试计划**：

| 测试文件 | 覆盖模块 | 测试数 | 优先级 |
|----------|----------|--------|--------|
| `tests/test_dashboard_utils.py` | utils.py（run_cmd, read_json, fmt_ms） | 15 | 高（8.1 前置） |
| `tests/test_dashboard_github.py` | github.py（mocked subprocess） | 10 | 中 |
| `tests/test_dashboard_agent.py` | agent.py（mocked file reads） | 12 | 中 |
| `tests/test_dashboard_metrics.py` | metrics.py（数据聚合逻辑） | 8 | 中 |
| `tests/test_dashboard_builder.py` | builder.py（集成测试，mocked 子模块） | 5 | 低 |

**工作量**：16h | **依赖**：8.1
**注意**：`test_dashboard_utils.py` 可在 8.1 拆分前先写（针对现有 `dashboard_data.py`），作为回归保护

---

### 8.4 Docker 隔离安全模型

**修复方案**：
```yaml
# deploy/docker-compose.prod.yml 增强
services:
  agent-runner:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp:size=100M
    networks:
      - agent-internal
    cap_drop:
      - ALL

  control-server:
    networks:
      - agent-internal
      - web-facing

networks:
  agent-internal:
    internal: true    # Agent 容器间通信，不暴露外部
  web-facing:
    driver: bridge    # 仅 control-server 对外
```

**涉及文件**：`deploy/docker-compose.prod.yml`
**工作量**：8h | **依赖**：无

---

### 8.5 Agent 角色扩展脚手架

```makefile
# Makefile
new-agent:
	@test -n "$(NAME)" || (echo "Usage: make new-agent NAME=my-role" && exit 1)
	@mkdir -p templates/agents/role-$(NAME)
	@for f in agent.json AGENT.md RULES.md TOOLS.md exec-approvals.json; do \
		cp templates/_scaffold/$$f templates/agents/role-$(NAME)/$$f; \
		sed -i '' "s/{{ROLE_NAME}}/$(NAME)/g" templates/agents/role-$(NAME)/$$f; \
	done
	@echo "✅ Created templates/agents/role-$(NAME)/"
	@echo "   Edit the files to customize your new agent role."
```

**涉及文件**：`Makefile`，新建 `templates/_scaffold/` 模板目录
**工作量**：4h | **依赖**：无

---

### 8.6 文档语言统一

**策略**：
- 代码注释、变量名：英文
- README.md：英文（附 `docs/README_zh.md` 中文版链接）
- 用户面向文案（setup.html、CLI 输出）：支持 `LANG` 环境变量切换
- i18n 实现：简单 JSON 文件 `i18n/{en,zh}.json`

**涉及文件**：全局，约 20 个文件
**工作量**：6h | **依赖**：无

---

### 8.7 PaaS 一键部署模板

```
deploy/
├── railway/
│   ├── railway.json          # Railway 配置
│   └── Procfile              # 启动命令
├── render/
│   └── render.yaml           # Render Blueprint
└── fly/
    └── fly.toml              # Fly.io 配置（可选）
```

```json
// deploy/railway/railway.json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": { "builder": "DOCKERFILE", "dockerfilePath": "Dockerfile" },
  "deploy": {
    "startCommand": "bash scripts/start.sh",
    "healthcheckPath": "/api/health",
    "healthcheckTimeout": 30
  }
}
```

**涉及文件**：新建 `deploy/railway/`、`deploy/render/`
**工作量**：4h | **依赖**：8.4（Docker 配置完善后）

---

### v0.8 验收清单

- [ ] `dashboard_data.py` 已拆分，无 >300 行文件
- [ ] 测试覆盖率 ≥60%（`pytest --cov` 验证）
- [ ] Docker 容器网络隔离，Agent 无外网直连
- [ ] `make new-agent NAME=xxx` 可生成完整角色模板
- [ ] Railway 模板可一键部署
- [ ] 文档英文为主，中文 i18n 可选

---

## Phase 4: v1.0 — 正式发布

> **目标**：生产就绪，具备完整生态能力
> **周期**：12-16 周 | **工作量**：~84h

### 1.1 Agent 模板市场 (16h)

**架构**：
```
marketplace/
├── registry.json            # 本地角色注册表
├── README.md                # 市场使用说明
└── cli/
    ├── install.sh           # openclaw-kit market install <name>
    ├── publish.sh           # openclaw-kit market publish
    └── search.sh            # openclaw-kit market search <keyword>
```

远端使用 GitHub Releases 或简单 JSON 索引文件托管。

---

### 1.2 可视化编排引擎 (24h)

**技术选型**：
- 前端：Vue 3 + Vue Flow（拖拽编排）
- 输出：`pipeline.json` 定义 Agent 调用链
- 运行时：`scripts/pipeline_runner.py` 解析 JSON 按序/并行调度 Agent

**范围**：v1.0 仅支持顺序编排 + 简单分支，不含循环/条件复杂逻辑。

---

### 1.3 E2E 测试套件 (12h)

```python
# tests/e2e/test_full_flow.py
class TestFullInstallFlow:
    """Mock OpenClaw gateway，验证从安装到启动的完整流程"""
    
    def test_bootstrap_creates_config(self, tmp_path):
        """bootstrap.sh 生成正确的 .env 和角色配置"""
    
    def test_start_launches_services(self, mock_openclaw):
        """start.sh 启动所有必需服务"""
    
    def test_watchdog_restarts_on_crash(self, mock_openclaw):
        """watchdog 检测到服务崩溃后自动重启"""
    
    def test_control_api_authenticated(self, running_server):
        """无 token 请求被拒，有 token 请求通过"""
```

---

### 1.4 多 IM 适配器实现 (12h)

基于 7.1 的 `IMAdapter` 接口，实现 Discord 和 Slack 适配器：
- Discord：使用 discord.py 或 HTTP API
- Slack：使用 Slack Bolt SDK 或 HTTP API

---

### 1.5 多项目 Dashboard (8h)

支持在同一 Web UI 中切换不同项目的 dashboard，配置存储在 `~/.openclaw-kit/projects.json`。

---

### 1.6 安全审计 (8h)

- 依赖扫描（Safety/Bandit for Python, npm audit for Node）
- 静态分析（Semgrep 自定义规则）
- 渗透测试（API auth bypass, XSS, path traversal）
- 输出安全报告 + 修复

---

### 1.7 发布准备 (4h)

- CHANGELOG.md 从 v0.5 到 v1.0 的完整变更
- 迁移指南（v0.5→v1.0 升级步骤）
- GitHub Release 自动化（CI/CD）
- 产品官网 landing page（可选）

---

### v1.0 验收清单

- [ ] 3 个 IM 适配器可用（飞书/Discord/Slack）
- [ ] E2E 测试通过率 ≥95%
- [ ] 安全审计零高危漏洞
- [ ] 角色市场 CLI 可用
- [ ] 可视化编排基础可用
- [ ] 完整迁移指南和 CHANGELOG
- [ ] 文档完整（英文 + 中文 i18n）

---

## 竞争力矩阵（v1.0 后）

| 能力 | OpenClaw Kit v1.0 | Soleur | OpenKIWI | CrewAI | OneClickClawd |
|------|-------------------|--------|----------|--------|--------------|
| 零第三方 Python 依赖 | ✅ 保持 | ✗ | ✗ | ✗ | ✗ |
| 多 IM 支持 | ✅ 3+ (飞书/Slack/Discord) | 1 | 2 | 0 | 1 |
| 细粒度角色安全 | ✅ tools.allow/deny + Docker 隔离 | 无 | Docker级 | 无 | 无 |
| 自愈监控 | ✅ watchdog + 指数退避 + 告警 | 无 | 无 | 无 | 无 |
| 角色市场 | ✅ CLI 市场 | 无 | 无 | Hub | 无 |
| 可视化编排 | ✅ Vue Flow | 无 | 无 | Studio | 无 |
| 部署方式 | ✅ 6+ (CLI/Web/Docker/Railway/Render/手动) | 2 | 3 | 2 | 1 |
| 本地模型 | ✅ Ollama 支持 | 无 | Ollama | 无 | 无 |
| 自学习能力 | 🔮 v1.1+ | 有 | 无 | 无 | 无 |

**核心护城河**：零依赖 + 安全模型 + 多部署 + 自愈 + 角色市场

---

## 风险登记簿

| ID | 风险 | 概率 | 影响 | 缓解策略 | 负责阶段 |
|----|------|------|------|---------|---------|
| R1 | dashboard 拆分引入回归 | 高 | 高 | 拆分前先补测试（8.3 前置部分并行于 8.1） | v0.8 |
| R2 | IM 抽象层过度设计 | 中 | 中 | 首版仅抽 send/receive，按需扩展 | v0.7 |
| R3 | Node 18 降级不兼容 | 低 | 中 | CI 矩阵测试 18/20/22 | v0.7 |
| R4 | WSL 边缘 case | 高 | 低 | 社区 beta 测试 + issue 模板 | v0.7 |
| R5 | v1.0 scope creep | 高 | 高 | 严守 v0.8 冻结后只做 v1.0 列表内任务 | v1.0 |
| R6 | OpenClaw CLI 上游变更 | 中 | 高 | 版本锁定 + 兼容性测试 | 全程 |
| R7 | 可视化编排引入重型前端依赖 | 中 | 中 | 按需加载 Vue Flow，不影响核心脚本 | v1.0 |

---

## 执行节奏与里程碑

```
Week  1     ─── v0.6 第1批 ─── 6.1,6.2,6.3,6.5,6.6,6.8,6.9 (无依赖，全部并行)
Week  2     ─── v0.6 第2批 ─── 6.4,6.7 (依赖第1批)
                                ⭐ Milestone: v0.6-rc → 安全审查 → v0.6 Release
Week  3-4   ─── v0.7 第1批 ─── 7.2,7.4,7.5,7.7 (无依赖，并行)
Week  4-6   ─── v0.7 第2批 ─── 7.1,7.3,7.6 (IM抽象层 = 关键设计)
                                ⭐ Milestone: v0.7-rc → IM集成测试 → v0.7 Release
Week  7-8   ─── v0.8 前置  ─── 8.3前置测试 + 8.2,8.5,8.6 (并行)
Week  8-10  ─── v0.8 核心  ─── 8.1 dashboard拆分 (关键路径)
Week 10-12  ─── v0.8 后续  ─── 8.3补全,8.4,8.7
                                ⭐ Milestone: v0.8-rc → 覆盖率验收 → v0.8 Release
Week 12-14  ─── v1.0 第1批 ─── 1.1,1.3,1.4 (市场+测试+IM)
Week 14-16  ─── v1.0 第2批 ─── 1.2,1.5,1.6,1.7 (编排+审计+发布)
                                ⭐ Milestone: v1.0-rc → 全面测试 → v1.0 Release 🎉
```

**总工作量**：~186 人时 ≈ 1 人全职 4 个月
**建议**：Week 7 (v0.8 开始) 前引入至少 1 名贡献者分担 dashboard 拆分和测试工作

---

## 附录：9 个现有 Agent 角色

| 角色 | 目录名 | 职责 |
|------|--------|------|
| AI 技术 | `ai-tech` | AI/ML 技术支持 |
| 热搜监控 | `hot-search` | 热点追踪与分析 |
| 公司运营 | `rd-company` | 日常运营管理 |
| 产品经理 | `role-product` | 需求分析与产品设计 |
| 代码审查 | `role-code-reviewer` | Code Review |
| 增长 | `role-growth` | 用户增长与营销 |
| 测试 | `role-qa-test` | QA 测试 |
| 技术总监 | `role-tech-director` | 技术决策与架构 |
| 高级开发 | `role-senior-dev` | 核心开发实现 |

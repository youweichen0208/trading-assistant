# trading-assistant

个人 Hermes gateway 的独立业务仓库，使用官方固定源码及插件，不 fork Hermes。

| 仓库 | 职责 |
| --- | --- |
| [youwei-webui](https://github.com/youweichen0208/youwei-webui) | 界面、登录、聊天历史和展示 |
| trading-assistant | gateway、平台 HTTP 工具、memory/知识、助手镜像和原生测试 |
| [youwei-trading-agent](https://github.com/youweichen0208/youwei-trading-agent) | Core/Controller/Runner、研究实验 Hermes、正式评估、跨服务兼容与部署备份调度 |

本仓库默认协作分支为 `develop`，变更通过 PR 合入；原 `main` 保留历史。开发、测试和构建不需要平台源码或兄弟目录。Core 仅通过 HTTP 访问。

## 独立开发与验证

```bash
uv sync --frozen --group dev --python 3.13
uv run --frozen pytest -q
docker build -f infra/images/hermes-assistant.Dockerfile -t trading-assistant:verification .
```

开发锁 `uv.lock` 只覆盖插件测试；运行镜像使用 `upstreams.lock.json` 记录的 Hermes 完整 SHA 和其原生 frozen 锁（messaging/mcp extras 与单独固定的 DDGS 可选依赖）。Python/uv 基础镜像 digest 固定在 Dockerfile；不把 Core 或研究环境依赖引入本仓库。

原生验收需要单独的固定 Hermes checkout，其安装方式：

```bash
git init /tmp/hermes-native
git -C /tmp/hermes-native remote add origin https://github.com/NousResearch/hermes-agent
git -C /tmp/hermes-native fetch --depth 1 origin f97608f178d1ffeca59860195ab7da295f7c8e5f
git -C /tmp/hermes-native checkout FETCH_HEAD
uv sync --project /tmp/hermes-native --frozen --no-dev --extra messaging --extra mcp --python 3.13
uv --no-config pip install --python /tmp/hermes-native/.venv/bin/python --require-hashes --no-deps -r infra/ddgs-requirements.txt
/tmp/hermes-native/.venv/bin/python ops/verify_assistant_native.py /tmp/hermes-native
```

脚本使用合成模型、本地临时 profile，无生产凭证或真实付费模型。CI 执行同样的单元测试、原生验收和镜像构建。平台另以显式 `--assistant-image` 验证 WebUI 组合；原生通过不等于跨服务、目标机或生产通过。

## 链路与边界

`Open WebUI（平台当前 v0.11.4）→ Hermes 原生 Chat Completions gateway → LiteLLM glm-5.3 / 搜索网页 / Core HTTP / 个人知识`

- Hermes 使用官方 **v2026.9.24 / v0.21.5**，固定 `f97608f178d1ffeca59860195ab7da295f7c8e5f`，独立 Python 3.13.16。镜像安装其原有锁中的 `messaging` / `mcp` extras 与 `infra/ddgs-requirements.txt` 中带 hash 的 DDGS 可选依赖，无上游补丁。入口长期运行 `hermes gateway run`，每轮原生 Agent 循环，不执行逐消息 CLI。
- [配置](integrations/hermes/config.yaml) 的 API 并发为 1，基础工具为 `web_search`、`web_extract`、`memory`、`youwei_platform`、`youwei_knowledge`，另加七项 EODHD MCP 查询工具。关闭 Tool Search 延迟装配、后台 review；启动时要求基础工具完整且全部工具处于允许列表，EODHD 离线仍允许基础助手启动，越界即退出。容器启用 init 回收子进程，禁用运行时 lazy installs。插件执行中间件再次限制工具名。无终端、通用文件、代码执行、浏览器、调度或自动技能安装工具。
- 搜索为固定版 DDGS 9.16.0。该版本配置示例提及的 `native` 提取器实际未注册；本项目通过插件注册 `youwei-public-page`，直接读取公共 HTML/text，复用上游连接时 DNS/IP 校验的 SSRF 客户端（包含重定向检查）。不使用付费源或匿名第三方提取代理。最多 5 URL、每页 2 MB / 30s 读取检查、正文 15000 字；PDF、动态页面不声称已完整读取。外层 Hermes 提取超时仍生效。查询时间随正文返回，发布日期须从材料本身核实。
- Core key 和专用 LiteLLM key 仅供助手服务使用；额外持有 EODHD 查询 key，不挂数据库凭证或 Docker socket。模型参数不接受 tenant 或任意 HTTP URL。当前单所有者，同一 profile 供跨聊天复用；不支持多用户共享个人记忆。
- 原生流式对话依赖请求消息历史。前端停止/断线不能被描述为 Core 任务已取消；普通聊天不保证重启后自动续跑。Core 已受理的任务仍由 Worker 持久执行，显式取消走任务接口。
- 正式 Campaign/Controller/Runner/研究实例不共享个人 profile、memory 或知识卷。本轮没有修改预测协议、批准 release、正式模型或训练配置；默认模型沿用已有 glm-5.3，不构成候选模型比较。

## 平台与知识接口

### EODHD 个人查询

个人查询通过 Hermes 原生 HTTP MCP 客户端直接连接 `https://mcp.eodhd.com/v1/mcp`。服务名 `eodhd`，仅开放 `resolve_ticker`、`get_stocks_from_search`、`get_historical_stock_prices`、`get_live_price_data`、`get_fundamentals_data`、`get_company_news`、`get_upcoming_earnings`；模型工具名为 `mcp__eodhd__<name>`。关闭 resources/prompts 自动工具，不自动接纳新增工具。

`EODHD_API_KEY` 仅注入助手运行环境，配置以变量引用 Authorization Bearer header；不放入 URL、镜像或模型参数。未设置 key 时禁用 MCP，便于隔离恢复。拒绝工具参数覆盖凭证；返回内容与 Python 日志脱敏。连接超时 10s，查询超时 30s，沿用上游连接恢复及退避。

公司名称先解析，美股默认 US；历史行情必须给日期区间，新闻默认 10 条，基本面默认 General/Highlights/Valuation，需要财报时显式请求 Financials。回答区分数据日期、币种、来源和实际时效，不声称所有报价实时。个人查询不自动进入 Core PIT 快照、Ledger 或 ResearchRelease。

原生验收包含 mock MCP 与 mock 模型。真实只读验证：通过私密环境注入 key 后运行 `python ops/verify_eodhd_live.py`，每项能力一次有界请求，仅输出状态及 schema hash。套餐拒绝会返回非零，不代表接线失败或允许自动采购。2026-10-04 VM 实测搜索、解析、历史、报价、新闻可用；基本面与财报日历被当前套餐拒绝。

### Core 接口

`GET /v1/data/daily-bars?ticker=AAPL&start_date=2026-09-01&end_date=2026-09-30[&as_of=…Z]`

租户 Bearer key 必须有效；管理员引导 key 不可替代。缺省 cutoff 从数据库时钟取得；拒绝未来或无时区 cutoff。证券按 `end_date` 解析（响应 `identifier_as_of`），返回单个永久 security 的已有日线。日期范围最多 3660 天。未知证券 404，非法范围/歧义 422；无行情为 `bars: []`，不填充。

响应标明 `frequency=daily`、`mode=forward`、`queried_at`、`as_of`、原 OHLCV/复权字段/quality，以及 raw object、source、vendor version、license tags、source_available_at/basis、ingested_at、usable_at。沿用系统实际可用时间 PIT；该接口不重新采集，也不是实时报价。

`youwei_platform` 映射现有研究提交、列表、状态、报告版本读取和取消。提交仅接受 ticker、horizon_td（1/20/60）和可选 benchmark_ticker，不传问题正文或个人记忆。幂等键来自原生执行中间件传入的 session/turn/tool-call 三元组；单次 HTTP 响应丢失自动重试一次且复用键。不同工具调用生成不同键。同一聊天请求被前端重新生成时可能有新执行身份，不承诺跨重新生成恰好一次；不确定错误先查状态/列表，不盲目创建新任务。

知识保存到独立卷，最多 2000 条、每条 256 KB；flat ID，不接受路径。保存记录 title/content/sources（url、accessed_at，published_at 可未知）、revision、hash。修订与删除要求当前 hash；写入原子替换，目录锁保护并发和备份，拒绝链接和特殊文件。修改保留递增版本号，**不提供逐修订历史回放**；删除后旧备份中可能仍留有内容。个人偏好使用 Hermes 有容量限制的 memory（2200/1375 字符），长篇资料使用知识工具。

## 镜像运行与交付

构建上下文仅本仓库。服务名仍为 `hermes-assistant`；入口 `/opt/youwei-assistant/entrypoint.py`，固定上游环境 `/opt/hermes`。挂载路径 `/var/lib/hermes/profile`、`/var/lib/hermes/knowledge` 及 UID/GID 10001 不变。

必填环境：`API_SERVER_KEY`、`YOUWEI_ASSISTANT_LLM_KEY`、`YOUWEI_ASSISTANT_CORE_KEY`、`YOUWEI_ASSISTANT_CORE_URL`。配置默认模型出口为 `http://litellm:4000/v1`。基础配置见 [config.yaml](integrations/hermes/config.yaml)，唯一工具允许列表见 [policy.py](integrations/hermes/policy.py)。bootstrap 生成 MCP 配置并验证原生发现，entrypoint 只负责启动；不要直接复制未展开政策的模板作为运行 profile。密钥只通过受控运行配置交付，不能提交到仓库或镜像。

运行限制、Compose 网络与资源、WebUI 单所有者切换、整体恢复操作由[平台手册](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/ops/hermes-personal-assistant.md)维护。

每次交付分别记录：本仓库完整 commit、Hermes 上游 SHA、Python/uv 基础镜像 digest、构建架构与镜像 ID、发布后的 registry digest、原生验收证据。源码提交和本地 image ID 不等于已发布镜像；平台登记消费助手 commit 和发布 digest，再验证兼容组合。个人助手升级可独立进行；研究/实验 Hermes 的归因补丁和 ResearchRelease 仍由平台管理。

## 镜像内备份工具

```bash
python /opt/youwei-assistant/backup.py create /tmp/hermes-data.tar.gz
python /opt/youwei-assistant/backup.py verify /tmp/hermes-data.tar.gz --destination /tmp/restored
```

创建操作在运行助手容器内执行。平台调度负责复制归档、记录运行 image ID/RepoDigests 和归档 SHA256，随后使用对应镜像在无网络、无生产卷的临时容器中验证。没有镜像元数据的旧备份必须显式指定已验证的 immutable 镜像，不能使用 latest 或跳过恢复。

### 备份语义

[备份模块](integrations/hermes/backup.py) 对 profile 根目录全部 SQLite 数据库执行 `sqlite3.backup()`；保存 `memories/`、`sessions/` 与锁内知识副本。排除 profile 配置、.env、插件和日志；部署密钥仍走原秘密归档。归档及目录权限受 `umask 077` 保护（WebUI 库本身含连接凭证，备份也必须按秘密保管）。

平台的 `chat_backup_verify.sh` 调用本工具将归档解到空的隔离目录，拒绝链接/越界成员，核对全文件 hash、数据库 integrity_check、知识可读取性。SQLite 文件各自一致，不承诺数据库、memory、notes 是跨存储原子事务。沿用 7 日 + 4 周保留；同机备份不构成独立故障域。恢复时停止助手，将隔离验证通过的 profile 数据和 knowledge 放回对应卷并修正 UID 10001，配置与插件由镜像重新安装。


## 迁移记录

2026-10-04 从 youwei-trading-agent 的 S12e 未提交实现迁入；插件及备份格式不变，上游未升级。助手源码、Dockerfile、原生验证及工具测试归本仓库，平台保留日线 API、数据库测试和 WebUI 配置/跨服务验收。无生产切换；实际验证记录见 [VERIFICATION.md](VERIFICATION.md)。

2026-10-04：按用户选择将个人助手对齐官方 Release；该 Release 的 Python 上界为 `<3.14`，个人助手独立环境因此采用 3.13。平台 Core 与研究 Hermes 的版本由平台分别维护，本次不变。镜像标签 `io.youwei.hermes.revision` / `io.youwei.hermes.release` 及 `/opt/youwei-assistant/upstreams.lock.json` 记录来源。

该官方 Release 自带 DDGS provider，但没有后来增加的 `ddgs` extra；为保持现有免 key 搜索，构建时单独安装带 SHA256 的四项固定依赖（DDGS 9.16.0 / primp 2.0.0 / lxml 6.1.2 / click 8.4.2），版本与前一已验证镜像一致，click 与 Release 锁一致。上游 pyproject/uv.lock 不修改，运行时仍禁止 lazy installs。

## 实现维护

`policy` 维护工具允许列表；`bootstrap` 负责 profile 安装与原生发现的连接清理；`registration` 注册工具，`handlers` 执行平台/知识调用并绑定运行身份。EODHD 查询约束与脱敏留在 `eodhd`。容器入口和原生验证共用这些实现。
平台与助手各自保留小型 mock 模型，维持独立测试；这不构成生产实现共享或兄弟目录依赖。

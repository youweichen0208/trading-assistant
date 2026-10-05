# 独立迁移验证（2026-10-04）

本文件保留各次验证的时间与结果，旧版本及当时未部署说明不代表当前状态。最新免费金融交付与生产证据见 [状态](docs/STATUS.md) 和平台 [金融上线记录](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/ops/trading-core-20261005.md)。

本仓库迁自平台 S12e，保留原插件字节、配置、五工具允许列表、容器路径和备份格式。Hermes 无补丁，未升级上游。

| 身份 | 值 |
| --- | --- |
| 助手源码 | 本仓库 Git 提交；平台候选锁引用完整 commit |
| Hermes 上游 | `7fa45eb349a1a6f1eebc010b3fef0a9d996f386a` |
| Python / uv 基础镜像 | `upstreams.lock.json` 与 Dockerfile 中各自的 digest |
| 本机构建架构 | linux/arm64 |
| 本地镜像 | `trading-assistant:split-verification` |
| 本地 image ID | `sha256:a55f802a7f9dab523d604d03d0585c28859653902e94b481905d94e9be11fd40` |
| registry 发布 digest | 未发布；不得将本地 image ID 当作已发布证明 |

实际执行（仓库根目录）：

- `uv sync --frozen --group dev --python 3.14.7`：独立安装成功，无 Core/Runner/兄弟目录依赖。
- `uv run --frozen pytest -q`：12 passed，无 skip；知识工具、Core HTTP 客户端、网页提取、SQLite/memory/知识备份恢复。
- `docker build -f infra/images/hermes-assistant.Dockerfile -t trading-assistant:split-verification .`：成功，构建上下文仅本仓库，使用固定基础镜像与 Hermes frozen 锁，复用对应固定构建缓存。
- `/tmp/youwei-assistant-hermes/.venv/bin/python ops/verify_assistant_native.py /tmp/youwei-assistant-hermes`：PASS，脚本先校验 upstream 完整 SHA；发现、401 鉴权、429 并发拒绝、流断开恢复、非法请求、平台调用身份、知识保存/跨聊天读取/修订/删除、完整历史/SSE、memory、备份/恢复/重启通过。使用真实固定 Hermes 和 mock 模型，不依赖平台源码。

跨服务组合验收由平台执行：`uv run --frozen python ops/verify_assistant_webui.py --assistant-image trading-assistant:split-verification` → PASS（固定 WebUI v0.6.36、旧聊天、追问/SSE、知识、重启、后台普通模型分流与镜像内无网络恢复）；详情记录于平台 S12g。CI 已配置独立安装、pytest、原生验收与镜像构建；本地执行结果不等同于远程 CI 运行结果。

未验收：目标机 amd64 镜像、资源和生产数据恢复、浏览器真实操作、真实付费模型、正式前向评估。未发布镜像、未切换生产、未修改 WebUI fork。

首次 GitHub CI 在安装解释器时失败：固定 uv 的内置下载清单找不到 3.14.7。CI 改用现有 Dockerfile 同一固定 Python 基础镜像运行测试；Docker 构建单独作业。未更换上游、Python 或 uv 版本。

修正后的 [GitHub CI](https://github.com/youweichen0208/trading-assistant/actions/runs/37143835375)（源码 `5279deaa3f40b4f07a0036d2fc63eb08247b1d97`）通过：独立依赖安装、12 项测试、固定 Hermes 原生验收及 Linux amd64 镜像构建。CI 构建未推送 registry，不等于目标机验收。后续提交仅同步文档中的平台 S12g 记录编号及此验收证据。

## 官方 Release 对齐：v2026.9.24（2026-10-04）

用户选择官方 v0.21.5 并明确同意个人助手切换至独立 Python 3.13；Core 与研究运行时不变。上游 tag 解引用到 `f97608f178d1ffeca59860195ab7da295f7c8e5f`，上游源码、pyproject.toml、uv.lock 均无修改（git diff --exit-code 通过）。

- `uv sync --frozen --group dev --python 3.13`、`uv run --frozen pytest -q`：12 passed；本地解释器 3.13.14，目标镜像固定 Python 3.13.16。
- 上游 `uv sync --frozen --no-dev --extra messaging --python 3.13`，之后 `uv pip install --require-hashes --no-deps -r infra/ddgs-requirements.txt`：通过；`uv pip check` 85 packages compatible。
- `/tmp/youwei-hermes-release-20260924/.venv/bin/python ops/verify_assistant_native.py /tmp/youwei-hermes-release-20260924`：PASS，发现、鉴权、并发拒绝、断流恢复、错误路径、五工具循环、完整历史/SSE、memory、知识修订/删除、跨聊天读取、备份恢复及重启。mock 模型，无生产凭证及付费调用。
- 首次尝试原有 `--extra ddgs` 被官方 Release 拒绝（未定义该 extra）。改为单独固定该可选 provider 的依赖；四个版本来自前一已验证 Hermes 锁，click 版本与此 Release 完全相同。没有修改上游依赖锁或源码。

本段记录提交前验证；目标 amd64 镜像、WebUI v0.11.4 组合、旧数据副本及生产切换由平台后续验收，最终部署证据保存在平台 `docs/ops/hermes-release-20260924-rollout.md`。旧段中的“未发布/未部署”是当时历史状态。
# EODHD MCP 接入（2026-10-04）

- `uv run --frozen pytest -q`：20 passed。新增允许列表、凭证覆盖拒绝、日期要求、默认新闻数量、错误和日志脱敏、启动边界测试。
- `/tmp/youwei-hermes-release-20260924/.venv/bin/python ops/verify_assistant_native.py /tmp/youwei-hermes-release-20260924`：PASS。真实固定 Hermes + mock MCP/model，覆盖七工具循环、明确允许列表、403/429/超时、凭证保护、MCP 离线启动，以及原有鉴权/并发/流式/历史/知识/memory/备份恢复/重启。
- MCP 依赖由上游原始 frozen lock 的 `mcp` extra 安装，Hermes SHA、Python 基线不变，无上游补丁。插件使用该 Release 的正式 MCP 模块导入路径；早期验收捕获的 deprecated-import 拒载已修复。
- VM 官方 MCP v1 握手、93 工具发现和七项有界只读请求完成：搜索、代码解析、历史行情、最新报价、新闻成功；基本面与财报日历为 subscription_denied。后两项不能宣称数据可用，不自动采购。未调用真实付费模型。
- 生产部署、镜像 digest、跨服务与恢复结果由平台的本次 EODHD 发布记录维护；本文件的本地通过不代替生产验收。

## 2026-10-04 模块重构（候选，未部署）

- 工具允许列表集中到 policy；profile 安装和原生发现集中到 bootstrap；注册与调用处理分离。
- `uv run --frozen pytest -q`：24 passed。
- 固定官方 checkout 的 `ops/verify_assistant_native.py`：PASS（鉴权、并发、流式、历史、memory、知识、备份恢复、重启；七工具 MCP、越界、凭证、脱敏、403/429/超时及离线启动）。
- `docker build -f infra/images/hermes-assistant.Dockerfile -t trading-assistant:refactor .`：本机 arm64 构建通过，无平台源码依赖。
- Hermes SHA、基础镜像、开发锁、工具名称、环境变量和备份格式保持原值。本轮未操作 VM，未调用真实付费模型或真实供应商查询；跨服务候选验收由平台记录。

## 2026-10-05 EODHD Extended 候选（生产切换阻断）

- 默认允许列表扩为 19 项，移除基本面/财报日历；基础五工具、官方 Hermes/Python/依赖锁保持原值。日期/年份、新闻及筛选数量、WebSocket 时长/消息数/字节数/连接超时在插件执行边界验证，凭证仅由服务端提供。
- TDD：新增允许工具测试先出现 1 项失败；查询限制测试出现 19 项失败；响应验收测试先因缺少实现失败。最终 `uv run --frozen pytest -q` 50 passed。
- 固定 checkout 的 `ops/verify_assistant_native.py`：19 工具循环、鉴权、允许列表、凭证/脱敏、403/429/超时/离线启动及原有流式/历史/记忆/备份恢复 PASS。
- `docker build -f infra/images/hermes-assistant.Dockerfile -t trading-assistant:eodhd-extended-candidate .`：arm64 独立构建通过。`docker run --rm --network none -v "$PWD:/verification:ro" --entrypoint python trading-assistant:eodhd-extended-candidate /verification/ops/verify_assistant_native.py /opt/hermes`：PASS，使用真实官方 schema 的 mock MCP；逐文件核对镜像内插件与验收源码一致。断流用例的 mock HTTP BrokenPipe 日志是预期关闭连接，不是验收失败。
- VM 现有 Key 通过官方远端 `tools/list` 发现 93 项，19 项目标 schema 已存 `ops/eodhd-schemas.json`。`ops/verify_eodhd_live.py` 按实际业务结构、证券及日期校验：15 项有效；盘中历史/技术指标/筛选为 subscription_denied；BTC-USD crypto WebSocket 为 connection_failed。没有合法空结果、限流或参数错误。
- 旧验收只看 MCP isError，会把技术指标/筛选嵌套 JSON 的 403 当成成功；本次增加解包与回归测试并重新运行所有查询。两项国债接口忽略 limit=1，分别返回指定年份内 1330/570 行，报告显式标记 limit_ignored。
- 全部真实调用只使用供应商查询，无付费模型。账户权限与实时采集未通过，按任务约束暂停生产切换，不删去失败工具。发布候选的源码、amd64 registry digest、跨服务结果由平台 `docs/ops/eodhd-extended-20261005.md` 记录；这不授予候选生产就绪状态。

## 2026-10-05 Marketplace 指数接入

- 当前发布恢复生产原有七项 MCP，并增加 `mp_indices_list` / `mp_index_components`，共九项 MCP + 五项基础工具。此前 Extended 候选保持历史记录，未被偷偷启用。
- TDD：允许列表先失败 1 项、Marketplace 参数边界先失败 6 项、结构验证先失败 1 项；实现后 `uv run --frozen pytest -q`：60 passed；`git diff --check` 通过。
- 官方固定 checkout 原生验收 PASS：九项工具循环、凭证覆盖拒绝、输出脱敏、403/429/超时/离线、流式/追问/历史/记忆/知识/备份恢复/重启。
- 本地独立 Docker 镜像构建及镜像内原生验收 PASS，Hermes/Python/依赖锁无改动。amd64/真实账户/跨服务/部署结果由平台最终发布记录维护。
- 官方 tools/list schema 新增 Marketplace 两项，参数为列表无必填及成分 `symbol`；限制单指数 JSON，保留历史成分原始日期，不生成 PIT 或历史权重结论。

- amd64 容器两次在验收脚本原有 30 秒启动等待窗结束前尚未就绪（首次与跨服务验收并行）；网关的退出信号来自脚本。启动等待增至 120 秒后重跑；MCP 业务查询超时仍为 30 秒，未改运行时参数。

2026-10-06 日期边界回归：金融包固定时间复现先失败后修复；助手日期错误提示先失败后通过。候选构建工作流在发布前运行固定 Hermes 原生 mock 和金融 fixture；不调用真实付费模型。提示词变化本身不保证每次模型回答正确。

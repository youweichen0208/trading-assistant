# 独立迁移验证（2026-10-04）

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

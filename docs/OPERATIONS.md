# 运行、交付与恢复

## 运行配置

容器入口为 `/opt/youwei-assistant/entrypoint.py`，固定 Hermes 位于 `/opt/hermes`；运行 UID/GID 为10001。profile 与 knowledge 分别挂载 `/var/lib/hermes/profile`、`/var/lib/hermes/knowledge`。

| 配置 | 用途 |
| --- | --- |
| `API_SERVER_KEY` | 原生 gateway 及只读技能服务鉴权 |
| `YOUWEI_ASSISTANT_LLM_KEY` | 助手专用模型网关凭证 |
| `YOUWEI_ASSISTANT_CORE_KEY`、`YOUWEI_ASSISTANT_CORE_URL` | Core 租户凭证与服务端地址 |
| `EODHD_API_KEY` | 服务端 MCP 查询凭证；未配置时不启用 MCP |
| `TRADING_SEC_USER_AGENT` | 应用名称与真实联系邮箱；未配置时 SEC 查询明确失败 |

真实值只存在受控环境文件；文档、源码、镜像和验收证据不保存它们。入口通过 bootstrap 展开工具政策，不直接将裸模板复制成最终 profile。skills 服务从相同镜像启动 `python /opt/youwei-assistant/workbench.py`，只读 profile，不需要金融、模型或 Core 凭证。

## 交付顺序

1. 在固定源码提交运行 [开发测试](DEVELOPMENT.md)，记录官方 Hermes SHA、金融源码/wheel hash 和补充依赖锁。
2. 构建目标 amd64 镜像，取得真实 registry digest；本地 image ID 和源码 tag 不能替代 registry 身份。
3. 平台登记兼容组合，运行新旧工具、真实来源、WebUI mock、备份恢复及 deployment 清单校验。免费核心来源不可用时保留候选。
4. 在已授权发布中，只更新计划中的服务，沿用已经核对的卷、网络和秘密；切换后检查健康、工作台鉴权、发现及代表性真实查询。

服务器路径、当前镜像、Compose与回滚配置统一查平台 [助手运维](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/ops/hermes-personal-assistant.md) 和 [上游管理](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/UPSTREAMS.md)。本仓无独立生产数据库迁移。

## 备份与恢复

镜像内 `backup.py create` 对 profile 根目录 SQLite 分别做一致副本，并保存 memories、sessions 与锁内知识；排除配置、插件、秘密和日志。平台将秘密单独归档，记录镜像与归档 hash，在无网络、无生产卷容器中验证恢复。

恢复需要匹配镜像与已验证副本，目标目录须为空；校验文件 hash、路径类型、SQLite完整性及知识读取。真实恢复先停止相关写入，恢复对应 profile/knowledge 并修正 UID。不同 SQLite 和文件不是跨存储原子快照，同机副本也不是独立故障域备份。详细已有命令及存储限制见 [README](../README.md)。

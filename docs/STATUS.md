# 状态与验收证据

截至2026-10-05，个人助手使用官方固定 Hermes v2026.9.24，已上线免费金融三工具、原有基础工具和九项 EODHD MCP；代码工具政策见 [policy.py](../integrations/hermes/policy.py)。工作台技能服务使用同一镜像的只读入口。

当前源码可能包含部署后的文档提交。运行版本只以平台 [上游管理](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/UPSTREAMS.md) 指向的发布锁与manifest为准，不把 develop HEAD 自动视为线上镜像。

| 证据层次 | 查阅位置 |
| --- | --- |
| 本仓迁移、上游切换、Extended失败和工具回归 | [VERIFICATION](../VERIFICATION.md)，按日期理解历史命令 |
| 免费金融候选及生产查询、SEC原文核对 | [金融部署](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/ops/trading-core-20261005.md) |
| 镜像、原生发现、WebUI mock、工作台鉴权、备份恢复 | 平台 [S12p发布证据](https://github.com/youweichen0208/youwei-trading-agent/tree/develop/infra/releases/20261005-trading-core) |

明确限制：工具允许不等于套餐授权；原有 EODHD 基本面/财报日历限制仍保留，Extended 十九工具候选未启用。免费历史不是正式 PIT。没有把 mock 模型验证描述为真实付费模型选工具质量，也没有执行正式前向评估。

本次统一文档只整理维护入口，不修改运行源码、依赖锁、供应商权限或生产版本。

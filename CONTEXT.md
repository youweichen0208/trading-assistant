# 助手领域术语

| 术语 | 含义 |
| --- | --- |
| Personal assistant | 单所有者 Hermes gateway；持久 profile、个人记忆和知识独立于正式研究 |
| Profile | Hermes 配置、会话、数据库和记忆所在目录；部署模板经 bootstrap 安装 |
| Tool policy | `policy.py` 定义的允许列表；不是供应商账户可用权限的承诺 |
| Platform task | 由 Core 接受并持久执行的研究任务；状态与取消以 Core 为准 |
| Call identity | session/turn/tool-call 三元组，用于绑定平台提交幂等键 |
| Personal knowledge | 带来源和当前内容 hash 的笔记；修订/删除校验当前 hash，不提供逐修订回放 |
| Finance worker | 同一助手容器中的固定可信 Python 子进程，调用 trading_core；不是通用代码执行器或 Sandbox Runner |
| Skills reader | 独立只读进程，复用固定 Hermes 读取接口；只展示技能，不运行正文模板 |
| Candidate image | 已构建的固定镜像；仍需数据、兼容和恢复验收后才能部署 |

正式研究术语以平台 [CONTEXT](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/CONTEXT.md) 为准，价格和财报口径以金融仓 [CONTEXT](https://github.com/youweichen0208/trading_core/blob/develop/CONTEXT.md) 为准。

# trading-assistant 工作指引

开始修改前读取 [CONTEXT](CONTEXT.md)、[文档索引](docs/README.md) 和 `git status --short`，保留已有未提交改动。中文沟通，英文代码命名。

- 修改工具或权限先读 [架构](docs/ARCHITECTURE.md)：`policy.py` 是工具允许列表的唯一来源，原生注册、发现及执行边界必须一致。新增能力优先用官方插件/配置，不修改固定 Hermes 上游源码。
- 金融获取与计算属于独立 trading_core；本仓只负责参数转换、注册、执行时限、取消、缓存和错误展示。Core 通过 HTTP 访问，不导入平台源码，不依赖兄弟目录安装。
- 修改入口、依赖或镜像先读 [开发测试](docs/DEVELOPMENT.md) 和 [运维](docs/OPERATIONS.md)。上游 SHA、基础镜像、补充依赖、金融 wheel 分别固定；金融安装保持所有已有上游包版本不变。
- 平台身份、Core/LLM/EODHD 密钥和 SEC 联系信息仅存服务端。模型不得传租户、凭证或任意地址/路径。生成代码由正式平台 Runner 授权执行，不通过个人助手绕过。
- 普通助手记忆、知识与免费历史查询不自动成为正式 PIT、Ledger 或批准研究版本。前端停止不代表取消已提交的 Core 任务。
- 权限或任务行为先写公共入口的反例测试，再实现；共享政策、依赖或跨模块变更后运行完整测试及相应固定 Hermes 原生验收。结果分为离线、真实来源、目标机与生产，不把 mock 当真实模型验证。
- 完成后更新 [状态入口](docs/STATUS.md) 或受影响文档；真实验收追加至 [VERIFICATION](VERIFICATION.md)，整体上线证据由平台维护。Conventional Commits，只包含本任务文件；部署依本次授权执行。

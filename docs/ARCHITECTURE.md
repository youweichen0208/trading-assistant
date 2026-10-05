# 助手架构

`WebUI → Hermes gateway → LiteLLM / 受限工具 → trading_core、EODHD、Core HTTP、个人知识`

## 模块

| 实现 | 职责 |
| --- | --- |
| [entrypoint.py](../integrations/hermes/entrypoint.py)、[bootstrap.py](../integrations/hermes/bootstrap.py) | 检查配置、安装 profile、发现工具、启动原生 gateway |
| [policy.py](../integrations/hermes/policy.py)、[registration.py](../integrations/hermes/registration.py) | 唯一允许列表、插件注册与工具描述 |
| [handlers.py](../integrations/hermes/handlers.py)、[core_client.py](../integrations/hermes/core_client.py) | 执行边界、调用身份与受限平台 HTTP |
| [finance.py](../integrations/hermes/finance.py) | 三个免费金融工具、固定 worker、总截止时间/取消/缓存 |
| [eodhd.py](../integrations/hermes/eodhd.py)、[web.py](../integrations/hermes/web.py) | 供应商参数与脱敏、公共网页提取及 SSRF 防护 |
| [knowledge.py](../integrations/hermes/knowledge.py)、[backup.py](../integrations/hermes/backup.py) | 个人笔记、内容 hash、SQLite/文件备份恢复 |
| [workbench.py](../integrations/hermes/workbench.py) | 同镜像的只读技能服务，单独进程和只读 profile 挂载 |

## 权威与权限

Hermes 管个人会话和运行；Core 管正式任务、租户、状态、取消与提交。普通回答不自动提交研究，知识和 memory 不批准 ResearchRelease。Core 已接受任务不会随浏览器断线自动取消。

基础工具与九项 EODHD MCP 的具体名称查 `policy.py`。免费日线/指标/财报默认走 trading_core；指数及指定 EODHD 的请求保留原工具，平台请求走 Core。供应商失败不静默换源。允许列表、工具发现和账户实际权限分别验证。

金融模块从固定 wheel 安装，不导入 Core 或复制金融算法。worker 只接受受控 JSON，受40秒总截止、单并发、取消回收及512KiB返回上限约束；成功结果最多16条、120秒内存缓存。它不继承 Core/LLM/EODHD 密钥，只接收必要环境及 SEC 联系配置。

密钥不进入浏览器或模型参数；助手不挂 Docker socket 或业务数据库凭证。技能读取关闭预处理，展示文本不执行内联 shell。正式生成代码执行仍归平台 Sandbox Runner。

## 存储和发布

profile 和 knowledge 分卷持久化，单所有者共享个人记忆。笔记当前 hash 用于并发修订保护，备份各 SQLite 库分别一致，不提供跨存储原子快照。镜像、卷路径、UID 和恢复流程见 [运维](OPERATIONS.md)。

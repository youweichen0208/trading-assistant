# 开发与测试

## 插件测试

仓库根目录，Python 3.13：

```bash
uv sync --frozen --group dev --python 3.13
uv run --frozen pytest -q tests/test_finance.py
uv run --frozen pytest -q
```

这些测试不需要平台源码、生产凭证或真实付费模型。开发锁包含 vendored 金融 wheel；`upstreams.lock.json` 与 Dockerfile 则固定实际 Hermes 运行环境。

## 固定 Hermes 原生验收

以下路径须是一次性测试 checkout，不能指向生产 profile 或另一任务的 checkout。若上游锁变化，按锁中的完整 SHA 更新命令；本示例对应当前固定版本。

```bash
git init /tmp/hermes-native
git -C /tmp/hermes-native remote add origin https://github.com/NousResearch/hermes-agent
git -C /tmp/hermes-native fetch --depth 1 origin f97608f178d1ffeca59860195ab7da295f7c8e5f
git -C /tmp/hermes-native checkout FETCH_HEAD
uv sync --project /tmp/hermes-native --frozen --no-dev --extra messaging --extra mcp --python 3.13
uv --no-config pip install --python /tmp/hermes-native/.venv/bin/python --require-hashes --no-deps -r infra/ddgs-requirements.txt
/tmp/hermes-native/.venv/bin/python infra/install_finance.py .
/tmp/hermes-native/.venv/bin/python ops/verify_assistant_native.py /tmp/hermes-native
```

金融安装步骤不可省略。安装器校验 wheel hash、已有依赖版本和完整兼容性；冲突时停止，而不是替换上游锁。原生验收使用临时 HOME、mock 模型与 MCP，不调用真实付费模型。

## 镜像验证

```bash
docker build -f infra/images/hermes-assistant.Dockerfile -t trading-assistant:verification .
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,size=256m \
  -v "$PWD:/verification:ro" --entrypoint python trading-assistant:verification \
  /verification/ops/verify_assistant_native.py /opt/hermes
docker run --rm --network none --read-only --tmpfs /tmp:rw,nosuid,size=128m \
  -e HOME=/tmp/finance -e HERMES_HOME=/tmp/finance/profile \
  -v "$PWD:/verification:ro" --entrypoint python trading-assistant:verification \
  /verification/ops/verify_finance_runtime.py
```

前两项验证镜像与本次源码对应，最后一项以固定行情/SEC响应验证金融原生入口。真实查询需要网络与服务端配置，金融脚本使用 `--live`；EODHD 使用 `ops/verify_eodhd_runtime.py` 及同目录的验证模块。切勿把历史十九项 `verify_eodhd_live.py` 默认探测当成当前九项发布验收。

CI 实际步骤见 [verify.yml](../.github/workflows/verify.yml)。WebUI 跨服务验收由平台显式指定两个固定镜像执行，不能从本仓单元测试推导通过。

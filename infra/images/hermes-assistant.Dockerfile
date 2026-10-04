# Native persistent gateway, isolated from the frozen research runtime.
ARG PYTHON_IMAGE=python:3.13-slim@sha256:bb2988715db2cf7ace7b53f38f3cffbef7c7046a656bee66245eb0ed386e2e81
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.16@sha256:440fd6477af86a2f1b38080c539f1672cd22acb1b1a47e321dba5158ab08864d
ARG HERMES_REVISION=f97608f178d1ffeca59860195ab7da295f7c8e5f
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS build
ARG HERMES_REVISION
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/* && git init /opt/hermes && \
    git -C /opt/hermes remote add origin https://github.com/NousResearch/hermes-agent && \
    git -C /opt/hermes fetch --depth 1 origin "${HERMES_REVISION}" && \
    git -C /opt/hermes checkout FETCH_HEAD && \
    test "$(git -C /opt/hermes rev-parse HEAD)" = "${HERMES_REVISION}"
WORKDIR /opt/hermes
COPY infra/ddgs-requirements.txt /opt/ddgs-requirements.txt
RUN uv sync --frozen --no-dev --extra messaging --python /usr/local/bin/python && \
    uv --no-config pip install --python .venv/bin/python --require-hashes --no-deps -r /opt/ddgs-requirements.txt && rm -rf .git
FROM ${PYTHON_IMAGE}
ARG HERMES_REVISION
LABEL io.youwei.hermes.revision="${HERMES_REVISION}" io.youwei.hermes.release="v2026.9.24"
COPY --from=build /opt/hermes /opt/hermes
COPY integrations/hermes /opt/youwei-assistant
COPY upstreams.lock.json /opt/youwei-assistant/upstreams.lock.json
ENV PATH="/opt/hermes/.venv/bin:${PATH}" PYTHONPATH=/opt/hermes \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/var/lib/hermes \
    XDG_STATE_HOME=/var/lib/hermes/profile/host-state \
    HERMES_HOME=/var/lib/hermes/profile YOUWEI_KNOWLEDGE_DIR=/var/lib/hermes/knowledge \
    API_SERVER_ENABLED=true API_SERVER_HOST=0.0.0.0 API_SERVER_PORT=8642 \
    HERMES_ENABLE_PROJECT_PLUGINS=false HERMES_DISABLE_LAZY_INSTALLS=1
RUN useradd --uid 10001 --create-home --home-dir /var/lib/hermes --shell /usr/sbin/nologin assistant && \
    mkdir -p /var/lib/hermes/profile /var/lib/hermes/knowledge && chown -R 10001:10001 /var/lib/hermes
USER 10001:10001
WORKDIR /var/lib/hermes
ENTRYPOINT ["python", "/opt/youwei-assistant/entrypoint.py"]

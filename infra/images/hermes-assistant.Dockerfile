# Native persistent gateway, isolated from the frozen research runtime.
ARG PYTHON_IMAGE=python:3.14-slim@sha256:51dafde81dbdb6ebde285137a295cf18a47ca95234fe388a343719cb97305b3d
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.16@sha256:440fd6477af86a2f1b38080c539f1672cd22acb1b1a47e321dba5158ab08864d
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS build
ARG HERMES_REVISION=7fa45eb349a1a6f1eebc010b3fef0a9d996f386a
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/* && git init /opt/hermes && \
    git -C /opt/hermes remote add origin https://github.com/NousResearch/hermes-agent && \
    git -C /opt/hermes fetch --depth 1 origin "${HERMES_REVISION}" && \
    git -C /opt/hermes checkout FETCH_HEAD && \
    test "$(git -C /opt/hermes rev-parse HEAD)" = "${HERMES_REVISION}"
WORKDIR /opt/hermes
RUN uv sync --frozen --no-dev --extra messaging --extra ddgs --python /usr/local/bin/python && rm -rf .git
FROM ${PYTHON_IMAGE}
COPY --from=build /opt/hermes /opt/hermes
COPY integrations/hermes /opt/youwei-assistant
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

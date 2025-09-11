ARG BASE_IMAGE=ubuntu:24.04
ARG COMMIT_SHA=""

# ---- builder ----
FROM ${BASE_IMAGE} AS builder
LABEL stage=builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata curl git openssh-client python3 python3-venv lsb-release && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Singapore

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

RUN mkdir -p /root/.ssh && \
    printf "Host github.com\nHostname ssh.github.com\nPort 443\nUser git\n" > /root/.ssh/config && \
    chmod 600 /root/.ssh/config
RUN ssh-keyscan -p 443 ssh.github.com >> /root/.ssh/known_hosts

# First: Copy in dependencies & install them, to have them cached even if project src changes
WORKDIR /src
COPY pyproject.toml uv.lock* README.md /src/
RUN --mount=type=ssh uv sync --all-extras --dev --no-install-project
# Now: Copy in Project source and build
COPY . /src/
RUN --mount=type=ssh uv build

# venv with system Python, then install the wheel there
RUN uv venv --python /usr/bin/python3 /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN uv pip install /src/dist/*.whl

# run usebench migration and put it in a nearby folder to copy
RUN mkdir -p /artifact/data && /opt/venv/bin/usebench-migration /artifact/data

# ---- runtime ----
FROM ${BASE_IMAGE}
ARG COMMIT_SHA
LABEL maintainer.Yuntong="Yuntong Zhang <ang.unong@gmail.com>"
LABEL maintainer.Leonhard="Leonhard Applis <leonhard.applis@protonmail.com>"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata curl wget git openssh-client python3 python3-venv lsb-release make tree ripgrep && \
    rm -rf /var/lib/apt/lists/*

RUN wget -O /etc/apt/sources.list.d/gitlab-ci-local.sources https://gitlab-ci-local-ppa.firecow.dk/gitlab-ci-local.sources
RUN apt-get update -y && apt-get install gitlab-ci-local -y
# bring only the ready venv and migrated data
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /artifact/data /app/data

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
ENV TZ=Asia/Singapore

# We saw that the agent sometimes re-iterated needlessly - given the experiment nature we can just install system packages. These are not production machines but throw-away containers. 
ENV PIP_BREAK_SYSTEM_PACKAGES=1 
RUN [ -n "$COMMIT_SHA" ] && mkdir -p /output && printf "%s\n" "$COMMIT_SHA" > /commit.sha || true

RUN apt-get update && apt-get install -y --no-install-recommends sudo && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 0 -o -g 0 app
USER app

WORKDIR /workspace

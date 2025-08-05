ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}
LABEL maintainer.Yuntong="Yuntong Zhang <ang.unong@gmail.com>"
LABEL maintainer.Leonhard="Leonhard Applis <leonhard.applis@protonmail.com>"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    lsb-release \
    openssh-client && \
    rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

RUN mkdir -p /root/.ssh && \
    echo "Host github.com\n\
    Hostname ssh.github.com\n\
    Port 443\n\
    User git" > /root/.ssh/config && \
    chmod 600 /root/.ssh/config
RUN ssh-keyscan -p 443 ssh.github.com >> /root/.ssh/known_hosts

WORKDIR /useagent

# Copy only dependency files first for cached install
COPY pyproject.toml poetry.lock* uv.lock /useagent/

# Install deps including private repos (requires SSH mount)
RUN --mount=type=ssh uv sync

# Run data migration from usebench
RUN uv run usebench-migration /useagent/data

COPY . /useagent/

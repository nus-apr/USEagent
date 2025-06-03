ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}

LABEL maintainer="Yuntong Zhang <ang.unong@gmail.com>"

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    lsb-release \
    openssh-client && \
    rm -rf /var/lib/apt/lists/*

# install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# make uv available in PATH
ENV PATH="/root/.local/bin:${PATH}"

# Create SSH config - only needed in certain environments
RUN mkdir -p /root/.ssh && \
    echo "Host github.com\n\
    Hostname ssh.github.com\n\
    Port 443\n\
    User git" > /root/.ssh/config && \
    chmod 600 /root/.ssh/config
RUN ssh-keyscan -p 443 ssh.github.com >> /root/.ssh/known_hosts

WORKDIR /useagent
COPY . /useagent/

# install all dependencies including usebench
# Use SSH forwarding, since uv may need to access private repositories
RUN --mount=type=ssh uv sync

# usebench data migration
RUN uv run usebench-migration /useagent/data

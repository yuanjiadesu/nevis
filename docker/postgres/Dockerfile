FROM postgres:16-bookworm

ARG PGVECTOR_VERSION=0.8.1

RUN apt-get update \
    && apt-get install --no-install-recommends --yes build-essential ca-certificates git postgresql-server-dev-16 \
    && git clone --depth 1 --branch "v${PGVECTOR_VERSION}" https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && make -C /tmp/pgvector \
    && make -C /tmp/pgvector install \
    && rm -rf /tmp/pgvector /var/lib/apt/lists/*

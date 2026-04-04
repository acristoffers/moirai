FROM fedora:latest

# Install MongoDB 7.0 (no Python packages from dnf — uv manages all of that)
RUN rpm --import https://www.mongodb.org/static/pgp/server-7.0.asc \
    && echo $'[mongodb-org-7.0]\nname=MongoDB Repository\nbaseurl=https://repo.mongodb.org/yum/redhat/9/mongodb-org/7.0/x86_64/\ngpgcheck=1\nenabled=1' \
        > /etc/yum.repos.d/mongodb-org-7.0.repo \
    && dnf install -y --setopt=install_weak_deps=False mongodb-org \
    && dnf clean all \
    && rm -rf /var/cache/dnf

RUN mkdir -p /data/db

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
COPY moirai/ moirai/

# Use Python 3.12 (pre-built wheels available for numpy/scipy)
RUN uv python install 3.12 \
    && uv sync --frozen --no-dev --python 3.12

ENV PATH="/app/.venv/bin:$PATH"

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Moirai web API
EXPOSE 5000

# Mount a volume here for persistent database storage
VOLUME ["/data/db"]

ENTRYPOINT ["/docker-entrypoint.sh"]

# Quayline, self-hosted. Issue 208.
#
# Two stages so the runtime image carries no build tooling and no test suite. The
# final image is python:slim with the package and the tariff corpus, nothing else.
#
# No pip install of dependencies, because there are none. `pip install --no-deps .`
# would be the same command with a disclaimer, and a reader would wonder what it was
# hiding. The build installs the project itself and nothing resolves from an index.

FROM python:3.13-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed AS build

WORKDIR /src

# The corpus is read at runtime from tests/fixtures/tariffs, resolved against the
# package rather than the working directory as of issue 208. It is copied before the
# install so an editable-free install picks up the same tree the tests ran against.
COPY pyproject.toml README.md ./
COPY src ./src
COPY tests/fixtures ./tests/fixtures
# The two data files the engine reads at run time. They are not package data, they are
# repository data an operator should be able to read and edit, so the image carries them
# at a path it names rather than burying them inside the wheel.
COPY config ./config

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --no-deps . && pip install --no-cache-dir --no-deps pytest

# Same digest as the build stage, on CodeRabbit's finding. A floating tag means a rebuild
# months from now produces a different base, and "it worked when we wrote it" becomes
# untestable. `tests/test_dockerfile.py` holds that in place.
#
# This is the manifest-list digest, not a per-architecture one, so the image is multi-arch:
# linux/386, linux/amd64, linux/arm64/v8, linux/arm/v7, linux/ppc64le. It is the same value
# `docker buildx imagetools inspect python:3.13-slim-bookworm` reports; a per-arch pin would
# be a different digest. Verified for arm64 by building all eight stages, and the Dockerfile
# and entrypoint make no architecture assumptions. Not verified by running: this repo's CI is
# amd64 with no qemu handler registered, so an arm64 container cannot execute here.
FROM python:3.13-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed

# curl is for the health check only. Python can do it without one, and a base image
# that carries a web client it does not otherwise need is a base image with a client.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Writable by nobody but the app user. The server keeps nothing on disk between
# requests, so this directory exists for the platform's own use, not ours.
RUN useradd --system --create-home --uid 10001 quayline
WORKDIR /home/quayline

# Both are read at import. Point them at the copies the build stage brought along,
# because inside site-packages the package-root resolution finds python3.13/ instead.
ENV QUAYLINE_CONFIG=/opt/quayline/config/audit.json
ENV QUAYLINE_CORPUS_DIR=/opt/quayline/tests/fixtures/tariffs
ENV QUAYLINE_FIXTURE=/opt/quayline/tests/fixtures/born_digital_invoice.pdf
COPY --from=build /src/config /opt/quayline/config
COPY --from=build /src/tests/fixtures /opt/quayline/tests/fixtures

USER quayline

EXPOSE 8765

# --chmod rather than a RUN chmod: this build environment refuses to chmod a file it
# just copied ("Operation not permitted"), and the mode is what COPY can set anyway.
COPY --chmod=755 scripts/container-entrypoint.sh /usr/local/bin/container-entrypoint

# Two processes, and the reason is in scripts/container-entrypoint.sh and
# docs/SELFHOST.md. The short version: the intake binds to loopback on purpose, and
# Docker's port proxy cannot reach a loopback listener inside a container.
ENTRYPOINT ["/usr/local/bin/container-entrypoint"]

# Loopback inside the container on purpose. The intake refuses a non-loopback bind
# because it holds a container number and a disputed amount and has no
# authentication, and that guarantee is worth more in a container than a convenience
# default. A deployment reachable from outside puts a proxy in front, and
# docs/SELFHOST.md says so with a working configuration.
# Through the forwarder, not straight to the intake, so the check exercises the same
# path a reader does. A health check that passes while every real request fails is
# worse than no health check.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl --fail --silent http://127.0.0.1:8765/healthz || exit 1

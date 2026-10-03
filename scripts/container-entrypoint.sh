#!/bin/sh
# Quayline container entrypoint. Issue 208.
#
# Two processes, and the reason is in docs/SELFHOST.md.
#
# The intake binds to loopback and refuses any other address, because it holds a
# container number and a disputed amount and has no authentication. Docker's published
# ports cannot reach a loopback listener inside a container, since its proxy connects
# to the container's own 172.x address. The forwarder bridges the two.
#
# This is a script rather than a shell one-liner in the Dockerfile ENTRYPOINT because
# `exec a & exec b` in a `-c` string did not survive contact with the shell: the
# forwarder never started and the container published an empty reply while reporting
# itself healthy. A supervisor whose failure is silent is worse than no supervisor.

set -eu

# Two ports, deliberately. The intake binds loopback and the forwarder binds every
# interface, and on Linux a wildcard bind collides with a loopback bind on the same
# number, so the first version of this script died with EADDRINUSE on start. The intake
# takes an internal port and the forwarder publishes a different one.
PUBLIC_PORT="${QUAYLINE_PORT:-8765}"
INTERNAL_PORT="${QUAYLINE_INTERNAL_PORT:-8766}"

quayline serve --host 127.0.0.1 --port "$INTERNAL_PORT" &
INTAKE_PID=$!

quayline-forward "$PUBLIC_PORT" "$INTERNAL_PORT" &
FORWARD_PID=$!

# Any of the three ways this can end should take the container down, not leave it
# half alive serving an empty reply.
trap 'kill "$INTAKE_PID" "$FORWARD_PID" 2>/dev/null || true' INT TERM

# Wait for whichever exits first, then stop the other. `wait -n` is not in POSIX sh,
# so this polls, which is uglier and works on every base image.
while kill -0 "$INTAKE_PID" 2>/dev/null && kill -0 "$FORWARD_PID" 2>/dev/null; do
  sleep 1
done

kill "$INTAKE_PID" "$FORWARD_PID" 2>/dev/null || true
wait 2>/dev/null || true

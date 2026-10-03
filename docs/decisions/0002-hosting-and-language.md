# 2. Hosting and language for the hosted and self-hosted product

Date: 2026-10-03. Issue 205. Decided by 10xdev4u-alt.

## Decision

**Hosting.** Single-region container on Fly.io or Railway. Not Kubernetes. Not a VPS
with a hand-written systemd unit, though that stays supported for self-hosting.

**Language.** Python, unchanged. No rewrite, no partial port.

**Distribution.** Docker Compose for self-hosting first, hosted second.

## Why not Kubernetes

It costs $3,500 to $11,000 a month for a small production cluster (encore.dev,
ESTIMATE) against about $25 for a PaaS at low scale (shippedsolo.com, ESTIMATE). The
crossover where a cluster is cheaper sits at $400 to $600 of PaaS spend per month
(cloudraft.io, ESTIMATE). All three are vendor estimates and they agree.

Beyond cost: this project has one service. Kubernetes is the right answer when
orchestration is doing work. With one process it is a control plane in exchange for
nothing.

The seven competitors read on 2026-10-03 included one running six services on
Kubernetes, with zero stars. That is the outcome to avoid, and it is already in the
wild.

**What would reverse this.** Two of: a hosted bill above $500 a month that is growing
predictably; or more than four services with cross-service networking. Both are
measurable and neither is true today.

## Why not Go

Go's advantage over Python here is distribution, not speed. PDF text extraction and
day-count arithmetic are not the bottleneck and will not become the bottleneck.

The specific friction a Go rewrite removes is a dependency graph, a wheel matrix and
interpreter drift. This repository has zero runtime dependencies. There is nothing to
remove.

The cost is the 46 CFR Part 541 encoding: 17,059 lines, 1,436 tests, 82 closed issues,
every section cited to a primary source. It is the only asset here a competitor cannot
reproduce in an afternoon, because reproducing it means reading the CFR.

**What would reverse this.** Two of: a distribution requirement the Python package
cannot meet after a real attempt, such as an air-gapped install with no interpreter
available; or a measured hot path where Python is the ceiling and the profiler names
it. Not a benchmark showing Go is faster in general.

If it is ever needed, the cheap version does not touch the engine. Ship a pinned
interpreter in one file, or a Go wrapper that embeds one. Both work today.

## Why self-hosting before hosted

Six competitors, six stars, and none of them installable by a non-author. The
association channel (NYNJFF&BA, TIA, NCBFAA, NMFTA) and the regulator both reach
people who will not create a hosted account, and whose objection to a hosted tool is
that a container invoice leaves their building.

Self-hosting is also the cheapest possible way to find out whether anyone wants this,
because it needs no account system, no database and no tenancy before the first user.

## What this decision does not cover

Accounts, per-account isolation, billing, and the audit log are not decided here. They
follow a second user, not a first, and issue 205 leaves them open deliberately.
# Platform, competition and distribution

Read on 2026-10-03. Issue 205. Everything here is dated, and the tiers say what kind
of claim each figure is.

This note answers one question: what should be built around the engine so that
somebody who is not the author can use it, and pay for it.

---

## The regulatory position, confirmed against outside sources

The engine's regulatory encoding was written before this research. Two checks came
back clean, which is worth recording because it means the previous work was right and
the open work is elsewhere.

**541.4 is gone.** *World Shipping Council v. FMC*, No. 24-1088, 152 F.4th 215 (D.C.
Cir. 2025-09-23) severed and vacated the "properly issued invoice" provision, and 90 FR
60580 removed it from the CFR effective 2025-12-29. `regulation/vacatur.py` cites both
and builds a kill switch so no check can key on the section. VERIFIED, confirmed
against three independent secondary sources on the date above.

**The burden sits with the carrier.** 46 U.S.C. 41310(b)(2) puts the burden of
establishing reasonableness on the common carrier in a charge complaint.
`engine/forum.py` carries this in a `BURDEN_TABLE` keyed by forum. VERIFIED.

This is the most commercially important fact in the note and it is newer than most of
the market material written about this category. The carrier must justify the charge.
A shipper's recomputation is not an assertion against a carrier's assertion; it is the
evidence the proceeding needs. VERIFIED.

What survives the vacatur matters and is narrower than what circulates: 541.6 still
requires the invoice to state the basis on which the billed party is liable, and
omitting a required element still eliminates the obligation to pay under 541.5.
541.7 and 541.8 are untouched. 541.4 now reads "[Reserved]". VERIFIED.

The September 1, 2026 final rule on charge complaint procedures extends the
traditional complaint route, where the carrier bears the burden of showing charges are
reasonable. VERIFIED, Federal Register, read on the date above.

---

## Competition: six projects, six stars

| Project | Stars | Shape |
|---|---|---|
| captv89/OpenDA | 6 | LLM extraction of disbursement accounts, human review |
| rickjeffsolutions/pilotage-core | 0 | Port fee cross-reference, Kubernetes microservices |
| freightbill/freightbill | 0 | Documentation site on LTL and FTL audit pipelines |
| four13co/freight-auditor | 0 | Empty skeleton, spec lives in ClickUp |
| indy-viberr/stowaway | 0 | Agent invoice fraud checking against live sources |
| Agsergio04/Fluster | 0 | Spanish, SME container cost tracking, React and Mongoose |
| wearewarp/warp-tools | 0 | A D&D calculator added as one port of a tools monorepo |

VERIFIED, read from the GitHub API on the date above.

Three things this table says.

**Nobody ships D&D audit as a product and gets adoption.** Every one of these is a
weekend project, a hackathon entry, an empty skeleton, or a documentation site. One
ships on Kubernetes with six services and has zero stars.

**The closest competitor uses an LLM for extraction and we do not.** OpenDA reads
physical scans with Docling and routes to an accountant. Quayline reads born-digital
PDF text with no OCR and no model. That is a real difference in failure modes: a
deterministic parser that cannot read a scanned invoice fails loudly, and a model that
guesses produces a confident wrong number. The repo already records the argument in
`ingest/`, including the fixture that shipped stating four free days from June 30 with
a July 7 end date.

**Two of these validate the same insight from outside.** stowaway's own README says
"No LLM in the money math. (tested)". PilotageCore grounds dispute text in "real D&D
cost from the published Maersk tariff", which is the same move as `tariffs/` here.

---

## Cost of hosting

| Source | Finding | Tier |
|---|---|---|
| encore.dev | Realistic small production cluster, $3,500 to $11,000 per month | ESTIMATE, vendor article |
| cloudraft.io | PaaS to Kubernetes crossover sits at $400 to $600 per month of PaaS spend | ESTIMATE, vendor article |
| shippedsolo.com | Solo SaaS, $25 per month low scale, $70 to $150 at $10K MRR | ESTIMATE, vendor article |
| vibereference.com | "The mistake to avoid: K8s when PaaS would do" | ESTIMATE, vendor article |

All four are vendor content with an interest in the answer. They agree on the shape
anyway: crossover between $400 and $600 per month of PaaS spend, and the
operator-hours cost of the gap is real.

At zero revenue the arithmetic is not close. Kubernetes is $3,500 a month before the
first invoice. PaaS is about $25.

---

## Language

The Go case is about distribution and it is well made. From three sources:

- TestSmith rewrote a Python CLI in Go and reported that the win was not speed: "They
  weren't shipping a tool; they were shipping a setup process."
- A fleet client went Python to Go across 9,000 hosts for a $7 MB static binary against
  a $180 MB Python image, and the same author wrote: "At 90 servers, I would have kept
  the Python client."
- Tarmac's survey of teams that left Python found selective specialization rather than
  migration. Discord rewrote one service. Pydantic rewrote its core in Rust and the
  API stayed Python.

This repository has **zero runtime dependencies**. Dev tools only: ruff, mypy, pytest.
There is no dependency graph to eliminate, no wheel matrix, no OpenSSL pinning problem.
The specific friction that justifies a Go rewrite is not present here.

What a rewrite would put at risk: 17,059 lines, 1,436 tests, and a primary-source
encoding of 46 CFR Part 541 assembled across 82 closed issues. That encoding is the
only thing here a competitor cannot copy in an afternoon, and it is the reason the
product can make a claim at all.

There is a cheaper path to most of the same benefit, if it is ever needed: a single
file that ships a pinned interpreter, or a Go wrapper that embeds one. Both are
supported today and neither touches the engine.

---

## Where the users are

Not on GitHub. The category's discovery surface is named in the sources read on the
date above.

**Trade associations.** NYNJFF&BA, incorporated 1917, over 100 regular members and 25
industry affiliates, has filed substantive comments on D&D billing with the FMC since
at least 2024. TIA describes itself as the professional organization of the $167
billion North American 3PL industry and is the US member of FIATA, which represents
more than 40,000 companies. NCBFAA and NMFTA sit in the same position. TIA's own
testimony puts the number of US companies importing or exporting at over 400,000, "the
vast majority small- or medium-sized".

These numbers are the associations' own characterisations in their own filings. VERIFIED
as their claims, not independently audited.

**The regulator.** The FMC takes charge complaints by email at
chargecomplaints@fmc.gov, from shippers, consignees, truckers, or others who paid or
were invoiced, with invoices, bills of lading and proof of payment.

**Content.** miragemetrics.com, cargolinked.com, tradlinx.com and gettransport.com all
carry "how to audit and dispute D&D charges" guides. Whoever ranks for that search is
doing the acquisition, and the guides are thin on the hard part.

---

## What this changes about the plan

The engine is done for the one carrier whose tariff is transcribed, and holds nothing
for eight others. The bottleneck is not code.

1. Run ten real invoices end to end. Issue 85. This is not a prototype. It is the only
   way to state a recovery rate, and AGENTS.md forbids stating one without
   measurement. Every competitor is claiming numbers from vendor-published and
   unaudited sources, which is the opening.
2. Make it installable by a person who is not the author. Docker Compose, one command,
   no Python knowledge. Self-hosting is a distribution decision, not a hosting budget
   decision, and it is the thing competitors have not done.
3. Only then add accounts and tenancy, because until there is a second user there is
   nothing to isolate.
4. Carrier submission stays last. Issue 62.
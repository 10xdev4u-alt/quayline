# Quayline

An invoice-self-auditing engine for U.S. ocean demurrage and detention disputes.

Quayline recomputes a charge from the invoice's own disclosures, compares it to
what the carrier demanded, and assembles the dispute.

## Why this works

46 CFR Part 541 makes a compliant D&D invoice self-documenting. Section 541.6(c)(2)
requires the carrier to name the rate rule it billed under. Section 541.6(c)(3)
requires the rate. Sections 541.6(b)(3), (b)(4), (b)(5) and (b)(8) require the
free-time allowance, both endpoints, and the specific dates charged.

So the whole charge can be recomputed from the invoice itself. No terminal API, no
carrier relationship, no data procurement. That is the product. The carrier-clock
data is the second layer, and it powers the availability argument and the annual
contract-amendment work.

## What it checks

| Check | Citation | Strength |
|---|---|---|
| Any of the twenty required fields missing | 541.5, 541.6 | **Automatic.** No cure period, no showing of prejudice |
| Invoiced more than 30 days after the charge was last incurred | 541.7(a) | **Wins on the face of the rule.** No evidence packet needed |
| Chargeable day count against the terminal gate calendar | 541.6(b), (c) | Arithmetic, not argument |
| Dollar total against the tariff, resolved from the carrier's own rate rule | 541.6(b)(8), (c)(2), (c)(3) | Arithmetic |
| Billed from a date earlier than the availability date the carrier itself disclosed | 541.6(b)(6) | Internal contradiction, no external data |
| Liability basis is generic filler | 541.6(a)(4) | Strongest hook surviving the vacatur of 541.4 |
| Published dispute window shorter than Part 541 allows | 541.6(d)(3), 541.8(a) | Arguable |
| Carrier affirmed the (e)(2) certification | 541.6(e)(2), 46 U.S.C. 41102(c) | Escalation path to civil penalties under 41107 |

## Three things that are true and that the category mostly gets wrong

**Free-time compression is a change in the charge unit, not the allowance.** Since
August and September 2024 every major carrier grants free time in working days and
charges post-free-time in calendar days. Same allowance, different unit, every box
past free time costs more. CMA CGM was already converted and is not part of that
cohort.

**Working-day and calendar-day is not one concept.** Hapag charges California
terminals in working days and every other gateway in calendar days, so a weekend
costs nothing in Los Angeles and two days at the tier rate in Savannah. CMA CGM
forgives every closed day in California. Maersk forgives nothing. Same container,
same weekend, three answers.

**MSC publishes no US import demurrage tariff at eight of the nine major
gateways.** It passes terminal demurrage through at cost. The controlling
instrument is the terminal operator's schedule. An MSC rules engine built from
carrier data produces plausible, silent, wrong answers.

## Status

Under construction. Nothing is merged yet. The issue set on GitHub is the
backlog.

## Contributing

Read [AGENTS.md](AGENTS.md) first. It is the contract: the eight stage pull
request loop, the six word commit subject, the co-author trailer, the merge policy,
and the branch cleanup that runs after every merge.

## Research

Everything we know is in `docs/research/`, dated and sourced. Claims are labelled
`VERIFIED`, `UNVERIFIED`, or `ESTIMATE`, and the label travels with the claim.

| File | Contents |
|---|---|
| [001-regulation.md](docs/research/001-regulation.md) | 46 CFR 541 encoded, 545.5, the case law, charge complaint procedures, the regimes not to conflate |
| [002-carriers.md](docs/research/002-carriers.md) | Per-carrier clock rules, free-time tables, the compression timeline, published waiver conditions |
| [003-integration.md](docs/research/003-integration.md) | Invoice ingestion, EDI transaction sets, carrier dispute channels, carrier developer APIs, TMS surfaces, terminal data |
| [004-evidence.md](docs/research/004-evidence.md) | Appointment screenshot specs, the interchange receipt, gate logs, customs holds, admissibility |
| [005-market.md](docs/research/005-market.md) | The pool, the competitors, the unit economics, the exit |

## Legal status

This is a compliance-audit tool, not legal advice. 46 CFR 541.5 and 541.7 create
rights. How they are asserted in a dispute is a matter of judgment and, in some
circumstances, of law. Findings that we believe but that have not been adjudicated
are marked `arguable`, never `high confidence`. Check with counsel before filing.

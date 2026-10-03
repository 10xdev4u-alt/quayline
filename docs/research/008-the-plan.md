# The plan to a product people can install

Written 2026-10-03. Closes nothing. Follows #205, and it is the answer to the question
in that issue: what gets built around the engine.

Every claim here is either measured from this repository, cited to a source in
`007-platform-and-distribution.md`, or marked ESTIMATE. Where the plan depends on
something unmeasured, it says so.

---

## The finding that reorders the work

While planning this, I traced what `engine/audit()` actually runs.

`regulation/checklist.py` encodes all twenty required disclosures from 46 CFR 541.6,
verbatim, with clause citations and import/export scoping. `regulation/kill_switch.py`
encodes 541.5. The specimen page renders the checklist. Tests assert the encoding is
correct.

    grep -c "CHECKLIST\|required_for\|by_cite" src/quayline/engine/audit.py
    0

**The audit runs none of them.** Six fields are required in `ingest/bind.py` only
because the ledger cannot be built without them, and a missing one raises
`OmittedError`, which aborts the audit instead of producing a finding.

So today an invoice missing a required disclosure crashes the audit, when the single
strongest finding the regulation supports was available the whole time.

### Why that is the whole ballgame

Coverage output, measured:

| | |
|---|---|
| Carriers with transcribed rates | 1 (Maersk) |
| Carriers we hold nothing for | 8 |

The recomputation is worthless for eight of nine carriers. Issue 174 asks which
carriers have rules but no transcribed rates and is measured in weeks per carrier.

**A 541.6 omission check needs no tariff at all.** It reads the invoice's own
disclosures against a fixed twenty-item list that is identical for every carrier, every
terminal, every trade. And 541.5 is automatic: no cure period, no showing of prejudice.
A missing required minimum **eliminates the obligation to pay the charge**.

Wiring this takes the product from 1 carrier to 9 with no acquisition work. Issue 207.

It is also the differentiator. Every competitor found in #205 does variance arithmetic
or LLM extraction. None does the disclosure check, because it requires reading the
regulation rather than an invoice. The four content guides that rank for "how to audit
and dispute D&D charges" all tell readers to check invoice contents first, by hand,
against a list they have to go and find.

---

## Sequence, and why it is this order

The ordering rule is: **do the thing that is cheapest per unit of coverage, and do not
build anything that needs a second user before there is a second user.**

| # | Work | Why here | Gate |
|---|---|---|---|
| 1 | Wire 541.6 into `audit()` (#207) | 1 carrier to 9, no acquisition. Cheapest coverage there is. | None |
| 2 | Self-hosted Docker Compose (#208) | No accounts needed, so it does not wait on user two. Tests installability, which is the gap all seven competitors share. | None |
| 3 | Ten real invoices (#85) | The only thing that makes a recovery rate sayable. | Needs 1 |
| 4 | Hosted, single tenant | Turns self-host interest into a hosted trial. Deliberately no tenancy yet. | Needs 3 |
| 5 | Accounts, isolation, audit log | A second user justifies it. Not a first. | Needs 4 |
| 6 | Carrier coverage (#174) and integrations (#65 to #70) | Now worth doing, because 1 produces traffic. Weeks per carrier. | Needs 3 |
| 7 | Carrier submission (#62) and `fmc/` | The complaint half. Expensive, and worthless before there is a recovery rate to point at. | Needs 6 |

Steps 1, 2 and 3 run in parallel. They touch different code and have no dependency on
each other.

---

## Step 1: make the check real

Issue 207 has the acceptance criteria. The engineering shape:

- `audit()` enumerates `CHECKLIST` filtered by `required_for(trade)`, raising one
  `DISCLOSURE_OMITTED` finding per missing field with its clause cited.
- `effect_of()` runs over the findings and the resulting `Obligation` reaches the
  result and the letter.
- A missing disclosure becomes a finding, never an `OmittedError`. The six fields in
  `bind.py` that abort are a different thing: without a total or a rate rule there is
  nothing to audit. Omissions are the finding, not an error in the auditor.
- Runs with `tariff=None` and still produces findings.

**Test shape that matters.** One test per omission class, on a real fixture, asserting
the clause. A test that asserts "there is an omission" passes if the wrong field is
missing.

**What could go wrong.** Extraction quality decides the answer. `coverage` already
lists `text_layer_incomplete` as a reason a field reads as absent. An omission the
carrier did not commit is worse than no product, because 541.5 is automatic and we
would be asserting non-payability from a failed read. The distinction must be carried
in the finding: *the carrier withheld this* versus *we could not read this*. The second
must not fire 541.5.

---

## Step 2: make it installable

Issue 208. Docker image, one-command compose, `docs/SELFHOST.md`.

Self-hosting before hosted is a distribution decision, not a hosting budget decision.
Seven competitors reviewed, zero installable by a non-author. The reachable channel is
NYNJFF&&BA, TIA, NCBFAA and NMFTA, whose members will not create a hosted account to
evaluate a tool and whose objection to cloud software in this category is that a
container invoice leaves the building.

For a forwarder handling other people's cargo, that objection is about cargo security
before it is procurement.

---

## Step 3: ten real invoices

Issue 85, unchanged. This is not a prototype and it is not optional.

`AGENTS.md` forbids stating a recovery rate without measurement. There is no
measurement, so there is no rate, so there is no pricing and no marketing claim. Every
competitor in the #205 table quotes vendor-published, unaudited figures. That is the
opening, and it closes the moment we guess.

The gates in `docs/research/006-phase-zero-gates.md` already exist and already set
them: recovery below 30 percent, or time per dispute above four hours, and the model
does not close. Run it and find out.

---

## Steps 4 and 5: hosted, then accounts

Step 4 is a hosted deployment of the same stateless engine, behind a real ingress with
TLS, offered so that someone who cannot self-host can try it. Single tenant, because
the current server holds nothing between requests by design (`serve/app.py`) and that
property is worth more than it sounds like.

Step 5 is where the product becomes a business: accounts, per-account isolation, an
audit log of who saw which invoice. Every one of those exists to answer "can I trust
this with my data", which is a question about a second user. Building them for one user
is speculative generality, and this repository has a recorded allergy to it.

---

## Step 6: carrier coverage and integrations

Now worth doing, because step 1 produces traffic and traffic produces invoices.

Issue 174 is the acquisition work: locate each carrier's current published schedule,
transcribe with provenance, mark `UNVERIFIED` where the schedule is not public. It is
weeks per carrier and it is the real moat, because reproducing it means reading
tariffs rather than reading an invoice.

Integrations (#65 to #70) are lower priority than they look. Every one of them adds an
external dependency, a rate limit, and a way for a number to be wrong in a way the
regulation does not cover. The disclosure check in step 1 gets most of the value with
none of that.

---

## Step 7: submission, and `fmc/`

The complaint half. Issue 62 is the carrier adapters; the missing package is `fmc/`,
whose content `regulation/evergreen.py` already holds as the three per-day proofs a
complainant must show per *Evergreen Shipping Agency v. FMC*.

Worth doing last because it is worth nothing before there is a measured recovery rate
and a carrier that responds. Both are step 3 and step 6.

---

## What this plan does not do

- **No rewrite.** Python, decided in `0002-hosting-and-language.md` with the reversal
  conditions recorded.
- **No Kubernetes.** PaaS, single region, until the bill passes $500 a month or there
  are more than four services.
- **No AI extraction.** The parser is deterministic and fails loudly, which is correct
  for a finding that eliminates an obligation to pay. Issue for OCR when a fixture
  demands it, and gate it on the same standard as everything else.
- **No feature built ahead of a user.** Everything above step 5 is justified by a
  measured input, and the inputs are named.

## The risk I cannot retire

Ten real invoices may show a recovery rate under 30 percent, or a time per dispute
above four hours, and the model does not close. In that case the correct outcome is to
publish the numbers and stop, not to look for the next feature.

`docs/research/005-market.md` says so in its own section on the exit, and that section
was written before any of this. It is the most useful document in the repository and it
predicts this moment accurately.
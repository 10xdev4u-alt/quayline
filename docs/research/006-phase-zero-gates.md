# Phase zero gates

Written 2026-10-01, before the experiment runs. Issue 86.

This document exists so the pass mark cannot be moved after the result is known. A
gate set afterwards is an argument, not a test. Everything below was fixed on
2026-10-01 against a repository at commit e1d61c5, with no experiment run and no
recovery figure measured.

## What phase zero is

Ten invoices, audited by hand, with no code in the loop. Issue 85. The question is
not whether the engine is well written. It is whether a person with the engine
beside them, reading ten real invoices, finds overcharges that collect.

Everything the engine can do is downstream of that answer. A correct
recomputation that finds nothing collectable is a fast way to confirm nothing.

## Why the gates are numbers and not opinions

Cost to serve is the binding constraint, not demand. `docs/research/005-market.md`
records an analyst cost of 45 to 95 dollars an hour for manual dispute work, and
days to weeks of elapsed time per dispute. That number is the reason the gates are
set where they are, and it is the reason gate two is a time gate and not a
satisfaction gate.

The derived cost of one dispute at the gate two threshold:

| Input | Value | Tier |
|---|---|---|
| Analyst rate, low | 45 dollars an hour | VERIFIED, `005-market.md` line 149 |
| Analyst rate, high | 95 dollars an hour | VERIFIED, `005-market.md` line 149 |
| Gate two threshold | 2 hours | Set by issue 86 |
| Cost at threshold, low rate | 90 dollars | ESTIMATE, 45 x 2 |
| Cost at threshold, high rate | 190 dollars | ESTIMATE, 95 x 2 |
| Kill threshold | 4 hours | Set by issue 86 |
| Cost at kill, high rate | 380 dollars | ESTIMATE, 95 x 4 |

So the band the manual process has to land inside is 90 to 190 dollars per dispute,
and the kill line is 380 dollars. If a real audit takes longer than four hours, the
cost to serve breaks before any accuracy question is reached.

**These are our arithmetic on a verified input.** They are not a vendor figure and
not a category benchmark. The 45 to 95 dollar rate is recorded in our own research
with a source line, and everything downstream of it is marked ESTIMATE because we
did the multiplication ourselves.

## The four gates

Each gate is pass or fail. No partial credit, no weighting, and no gate may be
dropped from the writeup after the run.

### Gate one, does the money collect

**Pass: at least 50 percent of identified overcharges collect.**

Recovery is measured as dollars actually credited, divided by dollars we identified
as overcharged. Not dollars invoiced, not dollars disputed. Credited.

Credits confirmed in writing by the carrier count. A carrier that acknowledges a
finding without issuing a credit does not count.

Why 50 percent. A dispute that wins on the law and loses on collection is not a
product. The category's own recovery figures are vendor published and unaudited,
and we do not inherit them as a floor.

### Gate two, can a person do this at all

**Pass: under two hours per dispute by hand.**

Measured per invoice, from the moment the PDF is opened to the moment the dispute
letter is ready to send. Include the extraction, the recomputation, the evidence
assembly, and the writing. Exclude waiting on the carrier.

Why 2 hours and not 4. Four is the kill line, and a gate set at the kill line
tests nothing. Two hours is the point where the cost to serve band above still
holds at the higher analyst rate.

### Gate three, does a carrier engage at all

**Pass: at least one carrier engages rather than auto-rejecting.**

Engagement means a substantive response. A carrier that acknowledges receipt and
resolves nothing does not count. A carrier that disputes the facts does count,
because a dispute is a conversation and a silent rejection is not.

Why this gate exists separately. It is possible to pass gates one and two on
invoices from a carrier that is simply wrong, and to fail in production because
every other carrier auto-rejects and the cost of that rejection is borne by the
shipper's relationship.

### Gate four, can this be run at all

**Pass: ten invoices are obtainable without payment.**

This gate is about feasibility, not quality. If ten real invoices cannot be obtained
at no cost, the experiment cannot run on a budget and the cost to serve arithmetic
above is optimistic by whatever the data costs.

Invoices that are public, that a shipper has already shared, or that arrive as a
matter of ordinary business all qualify. Invoices we buy to run the experiment do
not.

## The kill criteria

Any one of these stops the work. They are not a scorecard, they are tripwires, and
hitting any one of them is sufficient on its own.

| Kill criterion | Threshold | Why that number |
|---|---|---|
| Recovery below | 30 percent | Below this the fee economics in `005-market.md` do not close, and the gap to gate one is too wide to close by improving the engine |
| Time per dispute above | 4 hours | Cost to serve reaches 380 dollars at the high analyst rate, and `005-market.md` records the model breaking beyond two to four dispute operations people per account |
| Carrier engagement | none at all | If no carrier responds substantively across ten invoices, the filing path is not a product |

Note the deliberate gap between gate one at 50 percent and the kill at 30 percent.
A result between 30 and 50 is not a pass and not a kill. It is a result that
requires deciding whether to change the engine or change the market, and that
decision gets recorded in the writeup with its reasoning. Pretending the gap does
not exist would make both thresholds fiction.

## The writeup

Issue 85 produces it. It records, whatever the outcome:

- Every invoice, by reference, and how it was obtained, for gate four
- Hours spent per invoice, with what the time went to, for gate two
- Dollars identified as overcharged and dollars actually credited, per invoice, for
  gate one
- Which carriers responded and how, for gate three
- Each gate marked pass or fail
- The kill criteria checked one by one
- A stop or continue decision, in writing, with the reasoning

**The stop decision is recorded either way.** A pass is a decision to keep going
and a fail is a decision to stop, and the second one is written with the same care
as the first. An experiment whose writeup only appears when it went well is not an
experiment.

## What this document is not

It is not a prediction. Nothing here says the gates will be met, and no reading of
the engine's test suite implies anything about whether they will be. 1,207 passing
tests say the recomputation matches the tariffs we transcribed. They say nothing
about whether a real dispute collects.

It is also not permission to run the experiment early. Issue 86 gates the run, and
issue 85 is still open.
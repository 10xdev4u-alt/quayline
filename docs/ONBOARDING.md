# Quayline onboarding

Read this end to end before you touch code. It covers what the product is, the
rules it is built under, the work already done, the work left, and the mistakes
we have already made, because the mistakes are the part that will save you time.

If you disagree with something here, say so in an issue. This document is not the
authority. `AGENTS.md` is the authority, and where the two disagree, `AGENTS.md`
wins and this document is a bug.

---

## 1. What this is

Quayline recomputes a U.S. ocean demurrage and detention charge from the carrier's
own invoice, compares it to what the carrier demanded, and assembles the dispute.

**The insight that makes it work, and it is the whole product:**

46 CFR Part 541 makes a compliant D&D invoice self-documenting. Section 541.6(c)(2)
requires the carrier to name the rate rule it billed under. Section 541.6(c)(3)
requires the rate. Sections 541.6(b)(3), (b)(4), (b)(5) and (b)(8) require the
free-time allowance, both endpoints, and the specific dates charged.

So the entire charge can be recomputed from the invoice in your hand. No terminal
API. No carrier relationship. No data procurement. No competitor has this, because
everyone is buying container events and building a clock, and the regulation never
asked them to.

Carrier-clock data is the **second** layer. It powers the availability argument and
the annual contract-amendment work. It is not the foundation, and treating it as
the foundation is the single most expensive strategic mistake available in this
category.

### Three things the category gets wrong

These are documented in `docs/research/002-carriers.md` with sources. They are
here because they tell you what the engine has to encode, and every one of them
became a module:

**Free-time compression is a change in the charge unit, not the allowance.** Since
August and September 2024 every major carrier grants free time in working days and
charges post-free-time in calendar days. Same allowance, different unit, so every
box past free time costs more. CMA CGM was already converted and is not in that
cohort.

**Working-day and calendar-day is not one concept.** Hapag charges California
terminals in working days and every other gateway in calendar days, so a weekend
costs nothing in Los Angeles and two days at the tier rate in Savannah. CMA CGM
forgives every closed day in California. Maersk forgives nothing. Same container,
same weekend, three answers.

**MSC publishes no U.S. import demurrage tariff at eight of the nine major
gateways.** It passes terminal demurrage through at cost, and the controlling
instrument is the terminal operator's schedule. An MSC rules engine built from
carrier data produces plausible, silent, wrong answers. This one is in the README
because it is the clearest example of why `UNVERIFIED` is a real engineering state
and not a disclaimer.

---

## 2. The principles, which are not stylistic preferences

These are load bearing. Each one exists because removing it produces a specific,
named failure.

### The gate is defined exactly once

`make validate` is defined in the Makefile. The pre-push hook runs it, CI runs it,
you run it. There is deliberately no second list of checks anywhere, because two
lists drift and the drift is invisible until the day they disagree about what
passed.

### Claims carry a tier, and the tier travels

| Tier | Meaning | Where it may appear |
|---|---|---|
| `VERIFIED` | Read from a primary source we hold a copy of | Anywhere, with the citation |
| `UNVERIFIED` | Believed, sourced to a secondary or unavailable source | Only with the marker inline |
| `ESTIMATE` | Our arithmetic on verified inputs | Only with the inputs and the result shown |

Standing rules, all of them load bearing:

- Tariff data is transcribed from the carrier's own PDF and carries its filename,
  effective date, and publishing date.
- **A carrier that does not publish a number gets `UNVERIFIED`, not a guess.** We
  ship holes. Holes are cheap. Wrong rates are not.
- No recovery rate is claimed without measurement. The whole category's headline
  recovery figures are vendor-published and unaudited. We do not repeat them as
  fact and we do not infer ours from them.
- Legal conclusions are marked. A reading of Part 541 that we believe but that has
  not been adjudicated is `arguable`, never `high confidence`.

### The engine guesses nothing

This is the pattern you will see repeated in every module, and it is the single
most important idea in the codebase. **A type that cannot be misused beats a note
that explains the risk.** Three examples already shipped:

- `ClosurePolicy.extends_free_time_inferred` holds guessed entries separately, and
  `forgives()` takes `include_inferred: bool = False`. The guess is unreachable
  unless a caller names the doubt in the call. It used to sit in the sourced set
  with a `note` explaining it was a guess, and a note is skippable.
- `TextLayerStatus` reports `readable`, `present_unreadable`, or `absent`, and has
  **no accuracy score**. Character accuracy for born-digital text is near 1.0 and
  useless from there, so a number would be worse than no number, because a caller
  cannot tell a bad one from a good one.
- `Capture.captured_by` is required by the type. There is no way to construct a
  capture without a capturer, so there is no window in which unattributed evidence
  exists.

### Fail closed, and say which thing is missing

Three gates, one shape each: a single boolean with no severity field.

- `ValidationReport.can_file`
- `SubmissionReport.can_submit`
- `Packet.can_file`

A severity field is a field someone eventually passes as `False` and files anyway.
And when a gate blocks, it names the item, with the numbers in it. A carrier told
"validation failed" learns nothing and can answer nothing. A carrier told "the sum
of the lines is $4,760 and the total says $8,400" can answer the letter.

Related: **a blocked thing stays visible.** A `Packet` with a ground that has no
evidence is blocked *and still in the output*, marked `NOT FILED` with the reason.
Filing eight of nine claims and quietly dropping the ninth is how a partial win
becomes a total loss on the tenth, and the omission is only discoverable eleven
weeks later when the claim is time barred.

### Exact equality for self-consistency, tolerance for dispute

`engine/amount.py` applies a two percent band, and it is an `ESTIMATE` about
whether a dispute is worth filing. `ingest/validate.py` uses **exact** `Decimal`
equality, because it is not judging a carrier, it is asking whether a set of
numbers adds up to itself. A cent of difference is not a dispute, it is a
misparsed digit, and a two percent band would wave through a misparsed rate into a
demand letter as fact.

### Immutability and small files

Frozen dataclasses with `slots=True` throughout. A packet edited after assembly is
a packet nobody reviewed. Files are 80 to 570 lines, organised by domain.

---

## 3. The fleet: who does what

Two GitHub identities, both authenticated on a working machine:

| Account | Role |
|---|---|
| `10xdev4u-alt` | Repository owner. Writes most of the code. |
| `the-ai-developer` | Code owner and reviewer. Approves. Co-author on every commit. |

`CODEOWNERS` requires approval from one of these two, and branch protection has
`require_code_owner_reviews` on. The author cannot approve their own pull request,
so a change authored by one account must be approved by the other. That is the
intent, and it is enforced by configuration rather than by discipline.

**Know what this is not.** For every pull request so far, `the-ai-developer`
approval has been submitted by the same agent operating under the second account.
That satisfies CODEOWNERS and it is **self-review**. It is structural enforcement,
not substantive review. Issue #92 exists to decide what to do about this, and it is
the highest-value open issue in the repository, for the reason explained in
section 7.

### The agent roles available

This project is worked by agents with defined specialisations. The ones that
matter here:

| Agent | Used for |
|---|---|
| `planner`, `architect` | Decomposing a milestone, deciding module boundaries |
| `tdd-guide`, `python-reviewer` | Test-first discipline, Python review |
| `security-reviewer` | Anything touching input parsing, identity, or filing |
| `code-reviewer` | After every write |
| `plankton-code-quality` | Write-time formatting and lint |
| `principle-prove-it-works` | Before claiming anything is done |
| `loop-operator` | Long autonomous runs with stall detection |
| `blast-radius` | Before shipping a change that touches shared state |

---

## 4. The git cycle, and the full record

### The loop

`AGENTS.md` section two. No stage is skipped and no stage is reordered. One pull
request carries one issue to done.

```
 1. RESEARCH      read primary sources, not summaries
 2. EVALUATE      is this still true, and does it still matter
 3. ISSUE         bind the work to a numbered issue
 4. VALIDATE      prove the idea solves the issue before writing it
 5. BUILD         write the smallest change that closes the issue
 6. COMMIT        six word conventional commit, local validation green
 7. PUSH + PR     open the pull request, link the issue
 8. REVIEW        the-ai-developer or 10xdev4u-alt reviews
 9. VERIFY        reviewer validates against the issue, not against taste
10. MERGE         merge commit. never squash
11. CLEAN         remove local branch, remote branch, and any stale branch
12. REPEAT        next issue
```

Stage 9 is the one people get wrong. The reviewer validates against the **issue**,
not against taste. If the pull request solves the issue, it is correct even if the
reviewer would have written it differently.

### Commit rules, and the hook that enforces them

Exactly six words in the subject, conventional commit form. Exactly one trailer:

```
Co-Authored-By: the-ai-developer <the-ai-developer@users.noreply.github.com>
```

Enforced by `.githooks/check_commit_msg.py`, which runs two ways: as a pre-commit
hook via `.pre-commit-config.yaml`, and as a git `commit-msg` hook via
`.githooks/commit-msg`.

### Branch protection

`config/branch_protection.json`, applied by `scripts/configure_branch_protection.sh`.

- Merge commits only. Squash is **disabled**, rebase allowed.
- Branch deleted automatically on merge.
- One approving review required, from a code owner.
- Branch must be up to date before merge.
- All conversations resolved.
- No force pushes.
- `make validate` must be green.
- Linear history allowed, merge commits allowed.

The subtle part is in `docs/decisions/0001-protection-is-two-api-surfaces.md`:
merge methods live on the repository settings API, required reviews live on the
branch protection API, and the classic branch protection API has no field for
merge methods. Conflating the two surfaces is the main way this goes wrong. It
was verified live: a squash merge is refused with "the base branch policy prohibits
the merge" while `GET /branches/main/protection` returns 404.

### Every pull request so far, in order

Sixty-four merged, measured with `gh pr list --state merged`. The first five are
bootstrap, the rest are product. Four shipped no issue link, which is a process
gap rather than a problem with the work, and they are marked.

| PR | Issue | What landed |
|---|---|---|
| #91 | #75 | Toolchain: ruff, mypy, pytest, one `make validate` |
| #93 | #76 | Pre-commit hooks mirroring the gate |
| #94 | #77 | CI running the same gate |
| #95 | #1 | 541.6 twenty-field checklist, verbatim text |
| #97 | #78 | Enforceable branch policy |
| #99 | #3 | 541.7 deadline arithmetic, VOCC / MTO / NVOCC |
| #100 | #6 | 545.5 reasonableness factors as check hooks |
| #101 | #23 | ONE availability clock regimes as a dated lookup |
| #102 | #16 | Hapag customs-hold clock stop and its adverse side |
| #103 | #8 | Typed closure model, scheduled vs unscheduled |
| #104 | #12 | U.S. federal holiday calendar, observed-day shifting |
| #105 | #18 | Maersk working-day basis, Monday to Saturday |
| #106 | #9 | Charge windows and per-terminal day units |
| #107 | #11 | Hapag bank-holiday free-time extension |
| #108 | #29 | Day-count recomputation from disclosures |
| #109 | #30 | Arithmetic recomputation from the disclosed rate rule |
| #113 | #110 | Tolerance band moved out of the engine into config |
| #114 | #111 | Federal holiday set made a per-carrier parameter |
| #115 | #2 | 541.4 vacatur and the surviving 541.6(a)(4) hook |
| #116 | #40 | Born-digital PDF text layer parser |
| #117 | #42 | Deterministic validation layer |
| #118 | #112 | Inferred closure policy moved behind an opt-in |
| #119 | #63 | Per-carrier submission checklists |
| #122 | #59 | Evidence packet renderer, grouped by ground |
| #123 | #121 | Completed the `.githooks` hooks path |
| #124 | #61 | Capturer identity on every capture |
| #125 | none | This onboarding document |
| #127 | #126 | Tool artifacts ignored, and the index checked |
| #128 | #92 | The reviewer disposition rule, closing the panel question |
| #130 | #28 | Tariff resolution returning a result rather than a guess |
| #131 | #31 | Availability contradiction from the invoice alone |
| #132 | #32 | Freight term evidence for the liability basis |
| #133 | #129 | Co-author check tightened to the email address |
| #134 | #38 | The audit result contract and public surface |
| #135 | #34 | Findings ordered so automatic wins lead the letter |
| #136 | #37 | Typed warnings for the model limits |
| #137 | none | A lint for a recurring fixture mistake |
| #138 | #35 | Recovery estimate capped at the amount demanded |
| #139 | #39 | Corpus of transcribed tariff fixtures |
| #140 | #36 | Day-count findings demoted when the tariff resolves |
| #141 | #33 | The e2 certification test hook |
| #142 | none | Certification check renamed |
| #143 | #10 | Maersk appointment-demand closure rule |
| #144 | #4 | Process-only semantics for 541.8 findings |
| #145 | #5 | Two engines with different burden priors |
| #146 | #7 | Evergreen three-element per-day test |
| #147 | #22 | MSC charges normalised by physical locus |
| #148 | #24 | ONE partial shift and post-pull check |
| #149 | #25 | ZIM rules with rates marked UNVERIFIED |
| #150 | #15 | Hapag waiver conditions D06 and D07 |
| #151 | #13 | Hapag per-terminal schedules, no rates |
| #152 | #14 | Hapag detention schedules with required haulage |
| #153 | #17 | Maersk clusters and the PCD lock |
| #154 | #19 | CMA CGM bundle, Baltimore verified |
| #155 | #20 | CMA CGM California carve-out and rail |
| #156 | #21 | MSC pass-through lanes and the dedupe check |
| #157 | #26 | Evergreen terminal directory, five rows |
| #158 | #27 | Uncovered carriers registered with acquisition tasks |
| #159 | #41 | Table-aware charge line extraction |
| #160 | #49 | Content-hashed append-only ingest log |
| #161 | #46 | Terminal-plus-carrier double invoice detection |
| #162 | #48 | Money normalised before comparison |
| #163 | #44 | Multi-container lines and dispute groups |
| #164 | #45 | Credit notes as their own document type |

Probe pull requests #96 and #98 were opened to prove branch protection actually
blocks, then closed. Proving a control works is part of shipping it.

---

## 5. What the codebase looks like

18,733 lines across 85 modules, 1,555 tests, zero runtime dependencies. Dev tools
only: ruff, mypy, pytest.

Lines and modules measured at commit 7f7c066 with
`find src -name '*.py' ! -name '__init__.py' | xargs wc -l`. They have not moved
since, because nothing in this repository's history touches `src/` for a reason that
changes them without landing its own tests alongside.

The test count is **not** dated, and deliberately so. It moves on every pull request
that adds a test, so any commit named beside it would be a commit that does not
contain the tests it counts. It is asserted by `test_test_count_is_current` instead,
which fails on the pull request that makes it wrong.

Treat `make validate` as authoritative for all three.

```
src/quayline/
  regulation/   46 CFR Part 541 encoded, section numbers verified
    checklist.py      the twenty 541.6 fields, verbatim
    kill_switch.py    541.5, omission only. no arithmetic
    deadline.py       541.7 / 541.8 clocks, NVOCC chain, cure rights
    vacatur.py        541.4 vacated, 41104(f), liability-basis checks
    source.py         provenance primitive
  engine/       the audit checks and the recomputation
    identify.py       which carrier this invoice is, from the rule it discloses
    daycount.py       expected days from the invoice's own disclosures
    amount.py         expected money from the carrier's own rate rule
    recovery.py       which findings carry money, and which are diagnostic
    ordering.py       grounds, claims, ordering, strategy
    dedupe.py         demotes a day-count finding so dollars are not priced twice
    forum.py          the reasoned list the letter is written from
    availability.py   appointment and availability arguments
    warnings.py       model limits and coverage gaps
    reasonableness.py 545.5 factors
    settings.py       loads config/audit.json
  tariffs/      carrier data, one module per carrier, provenance on every block
    maersk.py, hapag.py, one.py, msc.py, zim.py, cma_cgm.py
    blocks.py, registry.py, corpus.py, resolution.py, terminals.py, uncovered.py
  calendars/    day counting
    holidays.py, closures.py, freetime.py, window.py, day_basis.py
  models/       the invoice as stated
    invoice.py
  ingest/       documents in
    pdftext.py        born-digital text layer, no OCR
    bind.py           the bound ledger, and what a missing disclosure means
    fields.py         541.6 field extraction and its citations
    validate.py       is the extraction internally consistent
  evidence/     evidence and filing out
    capture.py        who took it, when, digest of the bytes
    checklist.py      what each carrier will not accept without
    packet.py         grouped by ground, and rendered: the filing letter
  filing/       turning findings into something a carrier receives
    dispute.py        findings become grounds, with automatic claims first
    evidence.py       a checked capture, attached to a claim
  serve/        the local intake. Loopback only, no accounts, nothing on disk
    app.py            the HTTP handler and the three routes
    security.py       the one rule, and why there is no flag to widen it
    upload.py         the transport checks, before the engine sees anything
    audit_runner.py   the one seam between the CLI and the intake
    landing.py        the intake page's content, from the worked example
  web/          the pages and the design system
    design.py         every colour, measured step and duration, in one place
    intake.py         the rail, the day grid, the legend, the ledger
    reasoning.py      the engine's own sentence per day, with its citation
    result.py         the result page, rendered from structure not from markup
    failforward.py    what we read, what we could not check, and a letter to send
    filing.py         the printable filing copy, black on white
    specimen.py       the technical specimen, for a reader who wants the fields
    document.py       page assembly and the hash-pinned script
    money.py          how the money is worded, shared by both pages
```

**The two independent paths are the strongest signal in the engine.** A day count
wrong in one direction and a total that is right can both be plausible on their
own, and a carrier has to explain both. `engine/daycount.py` works out how many
days should have been charged; `engine/amount.py` works out what those days are
worth from the rate the carrier itself named. When they disagree, the finding is
much stronger than either alone.

---

## 6. What is done, and what is left

82 issues closed, 30 open, across six milestones. Measured at commit 7f7c066
with `gh issue list --state closed --limit 500 --json number --jq length` and the
same for `--state open`.

| Milestone | Open | Closed | What it is |
|---|---|---|---|
| M1 core engine | 0 | 42 | The recomputation. The regulation, the calendars, the tariffs. |
| M2 ingestion | 2 | 8 | Getting a document in and checking it. |
| M3 evidence and filing | 12 | 3 | Proving it, and sending it. |
| M4 integrations | 10 | 0 | Carrier and terminal APIs. |
| M5 platform and site | 6 | 5 | CLI, public site, the docs. |
| M6 validation | 6 | 0 | The phase zero experiment. |

**M1 is closed, all 42 of it.** Everything load bearing is built: the checklist,
the vacatur, the deadlines, both recomputation paths, the closure model, the
holiday calendar, the day-count arithmetic, and tariff modules for Hapag-Lloyd,
Maersk, CMA CGM, ONE, MSC and ZIM. Evergreen is present as
`regulation/evergreen.py`, which is the *Evergreen Shipping Agency v. FMC* case
holding a complainant to three per-day proofs, not a tariff, so it is in
`regulation/` and not in `tariffs/`. A carrier can appear in one without appearing in
the other and the distinction is the point.

**One carrier has transcribed rates, and the modules are not the same thing.**
`quayline coverage` is the authority: it prints that we hold rates for **one**
carrier, Maersk, and hold nothing for eight. A `tariffs/` module existing means a
carrier's schedule has been read and a structure exists, not that a rate resolves. The
distinction is the whole point of section 5's rules, and the fastest way to get it
wrong is to count modules.

An earlier version of this document ranked #28, #31, #32, #34, #37, #38 and #39 as
the top remaining work. All seven are closed. Pull requests #130 through #139
delivered them on 30 September. If you are reading that list somewhere, it is
history.

### The one structural gap, and it is not a milestone

This section used to say there was no spine. There is one, and it has been there
since #79 closed, so read this as history if you hit the old wording anywhere.

`engine/audit.py` provides `audit()`. `cli/` runs it from a terminal. `serve/` runs it
from a browser. `filing/` turns findings into grounds and grounds into the document a
carrier receives. `web/` is what a person actually looks at. The pieces are joined.

What is genuinely absent is `fmc/`. `AGENTS.md` section six lists it as a package under
`src/quayline/` and it does not exist, and the reason is that `regulation/evergreen.py`
already holds what was meant to go in it: the three per-day proofs a complainant has to
show, per *Evergreen Shipping Agency v. FMC*. Nobody has built the submission
machinery around those proofs, which is the complaint half of the product as opposed to
the recomputation half.

So the honest statement is narrower than the old one. **The engine recomputes, the
letter is assembled, and the complaint is not filed for you.** Everything needed to
submit to an FMC complaint exists as a rule and none of it exists as code. Issue #62 is
that work.

### The order I would take the remaining work in

**First, the submission path.** The spine landed in #79 and the letter after it, so
the remaining half is `fmc/`: the complaint itself, built from grounds the engine has
already priced. The CLI today gives a human triage
line, a JSON mode, and exit codes that distinguish no findings, filing-worthy
findings, and an engine error. #84 then reports what the engine does not know,
which is the same code path with a different question asked of it.

**Then M3, because filing is blocked on evidence.** Note the sequencing: #50
appointment screenshot spec and #51
per-day evidence come before #62 submission adapters, because an adapter that
sends an incomplete packet is worse than no adapter.

**M4 last among the product milestones.** The integrations are the most attractive
and the least important. Every one of them makes the product *look* more capable
without making a single existing claim stronger. This is the scope trap and it is
worth naming out loud to whoever is tempted.

**M6 is the milestone that decides whether this is a company.** #85 is ten manual
audits with no code. #86 sets the gates and kill criteria before running it. If
the engine does not reproduce the manual audits, everything else is a very
expensive way to be wrong. Do not skip M6 in favour of M4.

### The open decisions that are not yours to make

- **#92, reviewers outside the named panel.** Partly answered. PR #128 closed it
  by writing the disposition rule into `AGENTS.md` section one: judge the finding
  on its merits, and only involve identity when deciding to dismiss. What remains
  open is whether a human who is not the author ever reviews, which is a policy
  decision with real consequences and not one to decide alone. Section three of
  this document says plainly that every approval so far has been self-review under
  a second account.
- **#90, pricing from measured data.** Blocked on #85. Any number before the
  experiment is a guess we would have to defend.
- **#81, the visual system.** Depends on #80.

---

## 7. The failures we have already made

This is the section that will save you the most time, because every one of these
was found late and none of them was obvious.

**A parser that was character-perfect and still could not tell a valid document
from an invalid one.** The #40 fixture shipped stating four days of free time from
June 30 with an end date of July 7. Four days from June 30 is July 4. The parser
read every character correctly. It had no opinion about whether the document made
sense. That is the argument for #42, demonstrated by a shipped artifact rather
than a hypothetical, and it is the general shape of the risk here: **extraction
errors that are perfectly well-formed are invisible to the extractor.**

**A test suite that passed a bug because it asserted on the wrong part.** The PDF
parser was appending `) T` to every line. Every test passed, because every test
asked "is this string present" rather than "is this text correct". It took one
comparison against poppler's `pdftotext` to find it. That check is now a permanent
test. **If your parser has a reference implementation available, test against it.**

**A gate that enforced nothing and looked like it enforced everything.** For an
entire working session, every commit was made with
`git -c core.hooksPath=.githooks commit`. That directory contained
`check_commit_msg.py` and no `commit-msg` shim, so git found no hook, ran nothing,
and **exited 0**. A 7-word subject got through. The only reason it was caught was
a manual word count being run as a cross-check, which is a habit and not a gate.
Fixed in #123, and it then rejected my own next bad subject. **When a control
fails silently, the question is not "did it catch it" but "what was it pretending
to be".**

**Three tests that asserted things which were not true.** A wrong-typed capturer
"raises TypeError" (Python does not check argument types). A day list that
"summarises" (the suffix said `+7 more` while printing all ten dates). A retention
window that ran backwards and reported `-212` days remaining for a capture *inside*
its window. In each case the test checked the part that already worked. **A test
asserting something untrue is worse than no test, because it looks like coverage.**

**A fully compliant invoice, reported as a carrier who withheld a disclosure.** Every
line of the reference fixture is `Label: value`. A carrier invoice is not: it uses
columns, uppercase names, the carrier's own date style and different words. Against one,
the binder read 1 label out of 18 lines, and then raised `OmittedError` for 541.6(b)(4),
which says in its own message that this is "a finding against the carrier, not an
extraction fault".

The document states it, as `Free Time Commences  30-JUN-2026`.

So a compliant invoice became an automatic 541.5 finding that eliminates the obligation
to pay, and the claim gets printed, signed and sent. Issue 214. `ingest/bind.py`
documented this exact hazard in its module docstring and then had the bug, which is the
part worth remembering: **naming a danger is not building against it.**

There is now `UnreadableDocument`, raised when the layout is not one the binder reads,
and the choice is made per document rather than per field, because a document it reads
has real absences and a document it does not has only our failures.

**Every test in this repository used a fixture shaped like the parser.** Passing tests
proved the parser agreed with itself. The first document checked against the shape the
product will actually meet found a shipping blocker on the first try.

**Four pages that each said more than the engine could support.** All four were found
in review, and all four were prose written by hand rather than data read from the
result. The intake told a reader to **send a packet the packet gate rejects**, on the
page that states the packet cannot be filed. The reasoning panel called an unresolved
tariff a **dispute**, when the days may be right and the money is unknown. The ledger
called a **negative variance** disputed money, when the carrier billed less than the rule
allows. The day grid told one kind of carrier that free time covered their disputed day,
when `OVERBILLED` covers a day inside the allowance *and* a day after it that the
carrier's own day unit excludes, and the wording was only true of the first. Each one is
now a test, and in every case the fix was to make the page **ask the engine** rather
than to word it more carefully. `basis_of(code)` decides which finding carries money;
the page calls it. **Every sentence a page adds is a claim the engine has not made.**

**A second rendering of a document that already existed.** The result page stopped
parsing a rendered letter, which was right, and then wrote its own replacement, which
was not. It silently lost the line saying the packet cannot be filed, so a shipper
copying it sent a document which nowhere said it was not ready to send. The bug class
the change claimed to remove came back one pull request later. **Fixing a coupling by
replacing it with a second copy is not a fix**, and the test that should have caught it
asserted containment where it needed equality, because a document missing one line and
keeping everything else still contains the rest.

**Three defects that only a screenshot could find.** A stylesheet whose braces were
doubled, so the browser discarded every rule and the page rendered bare while a test
confirmed a `<style>` tag was present. A page that emitted the rail, the day grid, the
legend and the ledger and shipped CSS for none of them. A `font-family` with a weight
inside it, `800 system-ui`, which is invalid, so the heading meant to be a heavy
grotesque rendered as Times. None of these is reachable from a test suite that does not
render. **Look at the page.** The guard written afterward checks that every
class a page emits has a rule in the stylesheet that page ships, and that it ships no
rule belonging to another page. That catches the second. It does **not** catch the
third, and this document does not claim it does: a class-to-rule check cannot see that
`800 system-ui` is a weight sitting inside a family. **Say what a check covers.**

**An over-strict rule shipped knowingly.** The ONE power-of-attorney requirement
is `UNVERIFIED` and may block submissions ONE would have accepted. That is the
safe direction to be wrong in, and it is named in the code note rather than
assumed away, but it should not be the thing that gets skipped when someone wants
to ship a letter quickly.

---

## 8. Where the real opportunity is, if you want to innovate

Not a feature list. These are the four places where the work is structurally
advantageous and most competitors cannot follow quickly.

**The self-documenting invoice is a moat nobody has noticed.** Every competitor is
buying container event data and building a clock from it. The clock is a data
dependency, a procurement problem, and a model problem. Recomputing from the
invoice means **we can ship before we have a single data partnership**. The
strategic consequence is that our cost base does not scale with carriers onboarded,
which is the metric the whole category is valued on.

**Carrier-clock data is still worth having, for a different reason.** The
availability argument needs to know when the box was actually available, not what
the carrier said. That is the second layer, and it is worth real money, but it is
an argument built *on top of* a self-auditing engine, not a substitute for one.
Position it that way and the integration work is additive. Position it as the
foundation and we are a data company with a legal problem.

**The evidence layer is a differentiated product, not plumbing.** We already have
#61 (capturer identity) and #59 (grouped packets) and #63 (per-carrier
checklists). The insight in `docs/research/004-evidence.md` is that a UIIA panel
treats a clean gate-out receipt as an **allocation of liability**, and the
evidence standard is published and consistent. So we can match a published
standard rather than invent one. Issue #55, exploiting the missing-gate-record
finding from UIIA precedent, is the most interesting unopened issue in the
backlog, and it is the only one that lets us win without the carrier conceding
anything.

**Coverage as a product surface.** #84 asks for a coverage report listing what the
engine does not know. That sounds like an internal tool and it is the opposite: a
shipped, honest "here is exactly which carriers, terminals and claims we can and
cannot adjudicate today" is more persuasive to a shipper than any benchmark,
because a shipper does not trust a vendor who claims total coverage. The category's
credibility problem is precisely that its vendors overclaim.

### And the thing not to do

Do not start M4. The integrations are the most attractive work in the backlog and
the least valuable. Ten issues of carrier API work will make the product look
substantially more capable while making zero existing claims stronger, and it is
the standard way a project like this runs out of runway: impressive integrations,
no proof the engine works, and a phase zero experiment that never runs because
the integrations are always almost done.

---

## 9. First week

1. Read `AGENTS.md` in full. It is the contract, and this document is a summary of
   it that will drift.
2. Read `docs/research/001-regulation.md`. If you cannot explain why 541.5 is
   omission-only, you cannot work on the engine.
3. Run `make install && make validate`. Confirm a clean gate and note the test count.
4. Read `src/quayline/ingest/pdftext.py` and `src/quayline/ingest/validate.py`
   back to back. They are the clearest statement of the philosophy in the repo:
   a parser that refuses to guess, followed by a validator that fails closed.
5. Read `src/quayline/evidence/checklist.py` and notice that the whole file is
   `UNVERIFIED`. Ask yourself what it means to ship that, and whether the gate is
   honest enough about it.
6. Read `src/quayline/engine/result.py`, the `AuditResult` contract. Then grep
   for `def audit` in `src/` and find nothing. Everything the engine computes has
   no entry point, and closing that is the first work worth taking.
7. Pick up #79, and raise the missing-spine issue before you start it. The CLI is
   a thin layer over a function that does not exist yet, so the orchestrator is the
   real work and the command line is the proof.

When you open your first pull request, the reviewer's job is to validate it against
the issue, not against taste. Write the pull request body so that someone who has
not read the code can tell which acceptance criterion each part satisfies.

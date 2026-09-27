# Quayline agent operating manual

This file is the contract. Every agent that touches this repository reads it first
and follows it. It supersedes any earlier instruction on the same subject. Where
this file and a habit disagree, this file wins.

Quayline audits U.S. ocean demurrage and detention invoices under 46 CFR Part 541
and files the disputes. The engine recomputes a charge from the invoice's own
disclosures, because Part 541 forces the carrier to disclose the rate rule, the
rate, the free-time allowance, both endpoints, and the dates charged. The
recomputed figure and the amount demanded are then compared.

---

## 1. Accounts, identity, and authorship

| Role | GitHub account | Email | Used for |
|---|---|---|---|
| Owner, committer, reviewer | `10xdev4u-alt` | `10xdev4u@gmail.com` | All commits, all pushes, branch management, reviews |
| Co-author and second reviewer | `the-ai-developer` | (account email) | Sole co-author trailer on every commit; PR review |

Rules:

1. **Every commit carries `the-ai-developer` as the only co-author.** No other
   co-author trailer appears in history, ever. Verify with
   `git log --format='%B' | grep -c 'Co-authored-by:.*the-ai-developer'`.
2. **`10xdev4u-alt` is the sole committer identity.** Set it locally per clone:
   ```
   git config user.name  "10xdev4u-alt"
   git config user.email "10xdev4u@gmail.com"
   ```
3. **`the-ai-developer` reviews.** It is the default reviewer on every pull
   request. `10xdev4u-alt` may also review. At least one approval is required and
   the approving reviewer must be one of those two accounts.

   This is enforced, not merely expected. `.github/CODEOWNERS` names those two
   accounts as owners of every path, and `config/branch_protection.json` sets
   `require_code_owner_reviews`, so an approval from any other account does not
   satisfy the requirement. The count is 1, not 2, because an author cannot
   approve their own pull request.
4. Commit signing is off. Merge commits are on. Squash is off. Branch delete on
   merge is on.

---

## 2. The eight stage pull request loop

Work moves in stages. No stage is skipped, and no stage is reordered. One pull
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

### Stage 1. Research

Read the primary source. For this project that means the eCFR text of 46 CFR
Part 541, the carrier's own published tariff PDF, the FMC docket, the UIIA
decision. A blog post summarizing a tariff is not a source. A vendor's marketing
page is not a source for a recovery rate.

Record what was read, where, and when, in the pull request body. If a claim
cannot be sourced, mark it `UNVERIFIED` in the code and in the docs. Never fill a
hole with a plausible number.

### Stage 2. Evaluate

Three questions, in order:

- Is the fact still true? Tariffs are reissued monthly. Check the effective date.
- Does it change what we build?
- What is the cost of being wrong? A wrong rate in a dispute letter costs more
  credibility than a missing rate costs recovery.

Write the answer in the pull request body. An issue that fails this stage gets
closed with the reason recorded, not silently dropped.

### Stage 3. Issue

Every pull request closes exactly one issue. Every issue states the problem, the
evidence, and the acceptance criteria. An issue without acceptance criteria
cannot be validated at stage 9, so it is not ready.

### Stage 4. Validate the idea

Before writing the implementation, prove the approach works. Write the failing
test first. For engine work that means a test that encodes the real tariff number
from the real carrier PDF. If the idea cannot be shown to work on one real case,
it does not get built for the general case.

### Stage 5. Build

Smallest change that closes the issue. No drive-by refactors. No unrelated
formatting. A pull request that touches more files than the issue requires is a
pull request that cannot be reviewed.

### Stage 6. Commit and validate locally

Commit subject is **exactly six words** in conventional commit form:

```
<type>: <five more words>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `build`,
`ci`, `data`.

```
feat: encode hapag per-terminal detention schedules
fix: exclude scheduled closures from hapag shutout policy
docs: record maersk pcd lock in tariff provenance
test: cover cma cgm california weekend carve-out
```

Trailer, always:

```
Co-Authored-By: the-ai-developer <the-ai-developer@users.noreply.github.com>
```

Local validation runs before every push and must be green. **One command,**
because a list of commands is a list of ways to skip one:

```
make install    # first time only, creates .venv and installs the dev group
make validate   # the gate: pytest, ruff check, ruff format --check, mypy
```

`make validate` exits non-zero on any failure. A commit that cannot be validated
is not committed.

### Stage 7. Push and open the pull request

Branch name matches the issue:

```
feat/123-hapag-detention-schedules
fix/124-ca-carveout-weekend-charging
docs/125-tariff-provenance-format
```

Pull request body carries:

- `Closes #<n>`
- what was researched, with sources
- how the idea was validated before it was built
- the test that proves it
- what the reviewer should check

### Stage 8 and 9. Review and verify

`the-ai-developer` reviews first. `10xdev4u-alt` reviews when it is not the
author of the change. The reviewer checks the work against the issue's
acceptance criteria, not against personal taste.

Required review comment shape:

```
VERDICT: approve | request-changes
ISSUE: #<n>
ACCEPTANCE: each criterion, met or not met, with evidence
CITATIONS: each legal or tariff claim, verified or not
RISK: what breaks if this is wrong
```

`request-changes` is a normal outcome, not a failure. Fix, revalidate, re-review.

### Stage 10. Merge

**Merge commit. Never squash. Never rebase-merge a pull request that has
review conversation attached.** The history of the review is part of the record.

This is enforced at the repository level, not by branch protection. Squash
merging is switched off by `allow_squash_merge: false` in the repository
settings, because the branch protection API has no field for merge methods. See
`docs/decisions/0001-protection-is-two-api-surfaces.md`, and re-apply the whole
policy with:

```
scripts/configure_branch_protection.sh           apply and verify
scripts/configure_branch_protection.sh --check   verify only, change nothing
```

### Stage 11. Clean

After every merge, all three of these run. Skipping any one of them is the most
common way this repository becomes unmaintainable.

```
git checkout main && git pull --ff-only
git branch -d <merged-branch>
git push origin --delete <merged-branch>
git fetch --prune origin
git branch -D $(git branch --merged main | grep -v -E 'main|\*' | tr -d ' +')
```

Stale branch sweep, weekly or whenever the list exceeds ten:

```
git branch -r --merged origin/main | grep -v 'HEAD' | sed 's/ *origin\///' | xargs -r -n 20 git push origin --delete
```

### Stage 12. Repeat

Next issue. No batching two issues into one pull request.

---

## 3. Bootstrap ordering, which is not negotiable

This repository was brought into existence in a specific order, and the order is
part of the record.

1. Deep research on the market, the regulation, and the engineering
2. Full issue set raised on GitHub, sixty issues or more
3. First commit, which is the repository scaffolding
4. First pull request, which links the first issue
5. Then, and only then, the steady loop above

**No implementation work, no product code, and no feature commit happens before
the issue set exists.** A commit made before the issues were raised is out of
process and gets reverted.

---

## 4. Writing standards

The `unslop` skill is mandatory for every document, pull request body, issue
body, and code comment written in this repository. Read it before writing.

The rules that bite most often:

- **No em dashes.** Use a period or a comma. Reaching for parentheses instead just
  trades one tell for another.
- **Sentence case headings.** Not title case.
- **No AI vocabulary.** delve, crucial, landscape (abstract), pivotal, showcase,
  underscore, vibrant, tapestry, testament, robust, seamless.
- **No abstract metaphor nouns.** substrate, wedge, vector, locus, harness,
  scaffolding, bedrock, flywheel, north star, endgame, gold-plate.
- **No "not just X, but Y".** State the point.
- **No forced rule of three.** Use the natural number.
- **No bold on every proper noun.** Bold is for the one thing that matters on the
  line.
- **No inline-header lists** that restate the line after the colon.
- **Active voice.** Name the actor.
- **Concrete over abstract.** If the sentence could appear unchanged in another
  project's docs, it says nothing about this one. Cut it.
- **Have an opinion.** React to the fact. Do not neutrally list pros and cons.
- **Accurate content only.** No hype, no manufactured consensus, no invented
  citations.

**Clear data is the whole standard.** If a number in a document cannot be traced
to a source, it does not go in the document. If it is a vendor's self-reported
figure, it says so in the same sentence. If it is our own estimate, it says that
too, and it shows the arithmetic.

---

## 5. What the fleet is allowed to assert

Three tiers, and the tier travels with every claim.

| Tier | Meaning | Where it may appear |
|---|---|---|
| **VERIFIED** | Read from a primary source we hold a copy of | Anywhere, with the citation |
| **UNVERIFIED** | Believed, sourced to a secondary or unavailable source | Only with the `UNVERIFIED` marker inline |
| **ESTIMATE** | Our arithmetic on top of verified inputs | Only with the inputs and the result shown |

Current standing rules, all of which are load bearing:

- **Tariff data is transcribed from the carrier's own PDF** and carries its
  filename, effective date, and publishing date.
- **A carrier that does not publish a number gets `UNVERIFIED`, not a guess.** We
  ship holes. Holes are cheap. Wrong rates are not.
- **No recovery rate is claimed without measurement.** The entire category's
  headline recovery figures are vendor-published and unaudited. We do not repeat
  them as fact and we do not infer ours from them.
- **Legal conclusions are marked.** A reading of 46 CFR 541 that we believe but
  that has not been adjudicated is marked `arguable`, never `high confidence`.

---

## 6. Repository layout

```
src/quayline/
  regulation/     46 CFR Part 541 encoded, with section numbers verified
  engine/         the audit checks and the recomputation
  tariffs/        carrier data, one module per carrier, provenance on every block
  calendars/      day basis arithmetic and typed closures
  models/         the data model
  evidence/       capture, hashing, and certification
  ingest/         invoice and EDI extraction
  filing/         dispute packet assembly and carrier channel adapters
  fmc/            charge complaint preparation
  cli/            command line entry points
docs/
  research/       dated research notes, each with sources
  decisions/      architecture decision records
web/              the public site
tests/
data/             fixtures transcribed from real tariffs
```

Every module stays under four hundred lines. A file that needs to be split gets
split in the same pull request that made it too long.

---

## 7. Definition of done for a pull request

All of these, every time:

- [ ] Closes exactly one issue, with acceptance criteria met
- [ ] Six word conventional commit subject
- [ ] `Co-Authored-By: the-ai-developer` and no other co-author
- [ ] `make validate` green
- [ ] New code has tests that encode real data, not mocks of our own code
- [ ] Every legal or tariff claim carries a citation or an `UNVERIFIED` marker
- [ ] Written in the unslop standard
- [ ] Reviewed and approved by `the-ai-developer` or `10xdev4u-alt`
- [ ] Merged with a merge commit
- [ ] Local branch deleted, remote branch deleted, stale branches pruned

---

## 8. Standing prohibitions

- No squash merges. No exceptions for small pull requests.
- No co-author other than `the-ai-developer`.
- No force push to `main`. Ever.
- No force push to a branch that has an open pull request.
- No commit that skips local validation.
- No implementation work before the issue set exists.
- No number in any document without a source or an `ESTIMATE` label.
- No plausible-looking value standing in for a value we could not obtain.
- No merge with failing checks.
- No review approval from an account outside the two named above.

# 0001 Branch protection is two API surfaces, and one of them was empty

Date: 2026-09-27
Issue: #78

## Context

AGENTS.md section nine requires at least one approval from `10xdev4u-alt` or
`the-ai-developer` before merge, and section ten requires a merge commit and
prohibits squashing. Those rules were being followed by discipline, not by the
repository.

The claim in the bootstrap notes was that branch protection was in place. It was
not. `GET /branches/main/protection` returns 404 and the rulesets list is empty,
while `GET /branches/main` reports `protected: true`. That combination is
misleading: GitHub marks the default branch protected with no configured rules
attached.

Four pull requests merged under that state. The process held because the same
person was doing the work and the reviewing, and because the pre-push hook ran
the gate, but nothing in the repository would have stopped a `--admin` merge, an
unreviewed squash, or a force push to main.

## Findings

**Squash blocking is not a branch protection setting.** `allow_squash_merge`
lives in the repository settings, on `PATCH /repos/{owner}/{repo}`. The classic
branch protection API has no field for merge methods.

A squash merge on this repository is refused with "the base branch policy
prohibits the merge" while the protection endpoint returns 404. The refusal is
real and comes from the repository surface. A script that only writes branch
protection would leave squash available, and the acceptance criterion that groups
merge methods with the other protection settings invites exactly that mistake.

**`required_linear_history: true` is not stricter.** It forces squash or rebase
merging, which is the rule AGENTS.md prohibits. The correct value is `false` and
the name reads as though `true` were the careful choice.

**The branch protection API has no approver allowlist.** There is no field
restricting who may supply a required approval. `require_code_owner_reviews`
combined with a CODEOWNERS file is the only mechanism that expresses "an
approval from some other account does not count", so CODEOWNERS is the approver
allowlist.

**`required_approving_review_count` must be 1, not 2.** An author cannot approve
their own pull request. On a two account repository, requiring two approvals
means no change can ever merge.

## Decision

Split the policy into two objects in `config/branch_protection.json`, named for
the API surface each one is written to. `scripts/configure_branch_protection.sh`
applies the repository object first, then the protection object, then reads both
back from the live API and compares every field against what it sent.

The capability check runs before the first write. Issue 92 was a collaborator
discovered as a 403 partway through a sequence of calls, and a bare 403 does not
tell an operator which step failed.

CODEOWNERS is added so that `require_code_owner_reviews` has something to point
at. It only takes effect once merged to the default branch, so the script warns
rather than fails on the run that precedes that merge.

`restrictions` is left null. Any collaborator with push access may push to main.
Restricting pushes to one account would stop the other from opening a hotfix,
and the review requirement already covers the risk it would address. Recorded here
as a decision with a cost, not as an oversight.

## Consequences

`config/branch_protection.json` becomes the editable policy and AGENTS.md section
nine should point at it. Twenty tests read the JSON and fail if it stops
matching the manual, which is what makes the file trustworthy rather than merely
present.

The verify step in the script is what makes a partial failure visible. A script
that reports success after an unchecked write reports success on partial
failure, and the failure mode of this change was never "the write was refused",
it was "the write succeeded and was not what was intended".

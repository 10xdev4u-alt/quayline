"""Issue 36: two views of the same dollars, priced once.

The day-count check values overbilling as days times rate. The arithmetic check
values it as demanded minus recomputed. When the tariff resolves those are the
same money seen from two angles, and adding them prices the same dollars twice.

The evidence names the resolution: **when the tariff resolves, the variance is
authoritative and the day count becomes diagnostic.** The day-count finding stays
in the audit, stays in the letter, and keeps its order, because it is still true
and still worth sending. It simply stops carrying money, because the money is
already counted.

Why demotion rather than removal

A removed finding is a finding nobody can review. The letter still wants the
day-count argument — it is the computation the carrier has to follow — and a
packet that drops it reads as a letter that never checked. So the finding is
rewritten, not deleted: its code gains a `_diagnostic` suffix, and its detail
leading sentence says what happened and why.

The suffix is the mechanism. `engine/recovery.basis_of` reads codes, so a code
ending in `_diagnostic` falls through to no money without any special case, and a
caller filtering on the original code still finds it by prefix. Both properties
are asserted, because a demotion that is invisible to either side is a demotion
that does not work.
"""

from __future__ import annotations

from quayline.engine.result import CODE_DAYCOUNT_VARIANCE, Finding

#: The suffix. One string, in one place, so the recovery side and the tests agree
#: on what a demoted finding looks like.
DIAGNOSTIC_SUFFIX = "_diagnostic"

#: The note, verbatim. It is a constant rather than assembled because every demoted
#: finding says the same thing, and a constant is reviewable in one place.
DEMOTION_NOTE = (
    "Demoted to diagnostic: the tariff resolved, so demanded minus recomputed is "
    "authoritative and this finding values the same dollars. It remains in the "
    "audit and in the letter, and carries no money."
)


def demote_daycount(findings: tuple[Finding, ...], *, tariff_resolved: bool) -> tuple[Finding, ...]:
    """Rewrite day-count findings as diagnostic when the tariff resolved.

    Pure. The input tuple is untouched and the output carries the same findings in
    the same order, with day-count codes suffixed and the note prepended to their
    detail. Everything else passes through unchanged, including informational codes
    and codes nobody classified, because demotion is about one specific overlap and
    not a general rewriting pass.
    """
    if not tariff_resolved:
        return findings
    out: list[Finding] = []
    for finding in findings:
        if finding.code == CODE_DAYCOUNT_VARIANCE:
            out.append(
                Finding(
                    code=finding.code + DIAGNOSTIC_SUFFIX,
                    cite=finding.cite,
                    summary=finding.summary,
                    detail=f"{DEMOTION_NOTE} {finding.detail}".strip(),
                    grounds=finding.grounds,
                    days=finding.days,
                )
            )
        else:
            out.append(finding)
    return tuple(out)


def is_diagnostic(finding: Finding) -> bool:
    """Whether a finding was demoted. The recovery side reads this."""
    return finding.code.endswith(DIAGNOSTIC_SUFFIX)


def original_code(finding: Finding) -> str:
    """The code before demotion, so a filter on the original still matches."""
    code = finding.code
    if code.endswith(DIAGNOSTIC_SUFFIX):
        return code[: -len(DIAGNOSTIC_SUFFIX)]
    return code


__all__ = [
    "DEMOTION_NOTE",
    "DIAGNOSTIC_SUFFIX",
    "demote_daycount",
    "is_diagnostic",
    "original_code",
]

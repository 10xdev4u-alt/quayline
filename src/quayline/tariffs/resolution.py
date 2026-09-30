"""Issue 28: what tariff resolution does when it cannot answer.

The rule this module exists to enforce, stated once:

**A resolution failure is a valid, useful answer. A wrong rate is not.**

541.6(c)(2) makes the carrier name the rule it billed under, so when a carrier
complies the lookup is possible and any divergence between the looked up schedule
and the demand is a dispute rather than an opinion. That is the condition the whole
product depends on. What it does not guarantee is that *we* hold the schedule the
carrier named, and coverage is not uniform:

- Hapag publishes per terminal. Finest in the industry, and the reference case.
- Maersk publishes per cluster, several dozen combinations for one carrier.
- ONE has no static rate table at all. A calculator plus dated advisories.
- MSC publishes no U.S. import demurrage tariff at eight of the nine major
  gateways, so the controlling instrument is the terminal operator's schedule.
- ZIM's mapping is `UNVERIFIED`.

So "we do not have this" is a normal, frequent answer and the type has to say it
plainly. The previous resolver raised, which is defensible and unhelpful: an
exception is a control flow event, so every caller either catches it or crashes,
and a caller that catches it has nowhere to put a warning for the letter. This
module returns a value. ``Resolution.block`` is ``None`` when we cannot answer, and
``Resolution.warnings`` says which of the several distinct reasons applies, because
they are different problems with different fixes.

What it refuses to do

Three refusals, and they are the substance of the issue.

1. **It will not approximate.** No nearest match, no fuzzy key, no fallback to a
   sibling cluster or a neighbouring date. A comparison against a rate the carrier
   never said applied would be presented as a dispute, which is the failure mode
   this repository has spent six issues auditing out of itself.
2. **It will not resolve an ``UNVERIFIED`` block.** Holding a rate we could not
   transcribe confidently is not the same as holding it. An incomplete
   transcription resolves to ``None`` with a warning, so it can never become a
   number in a demand letter.
3. **It will not guess a missing dimension.** Hapag's detention schedules are
   indexed by haulage mode, read from a bill of lading checkbox. A detention query
   with no haulage mode is the fifteen to twenty percent error from issue 14, and
   it comes back ``None`` with a warning naming the missing input.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from quayline.tariffs.blocks import RateBlock


class Granularity(StrEnum):
    """How finely a carrier indexes its rates.

    Not a quality ranking. Coarse is not worse than fine, it is a different shape of
    lookup, and a registry that treats a calculator as a deficient table will try to
    make it into one.
    """

    #: One schedule per terminal. Hapag.
    PER_TERMINAL = "per terminal"
    #: One schedule per cluster or region. Maersk.
    PER_CLUSTER = "per cluster"
    #: No static table. A calculator plus dated advisories. ONE.
    CALCULATOR = "calculator, no static table"
    #: Rates come from the terminal operator, not the carrier. MSC at most U.S.
    #: import demurrage gateways.
    TERMINAL_OPERATOR = "terminal operator's schedule"
    #: We hold nothing and we know we hold nothing.
    NONE_HELD = "nothing held"


class Dimension(StrEnum):
    """An input a rate rule is indexed by, which a query may therefore lack.

    An enum because a warning has to name the thing that is missing, and a string
    assembled at the call site is a string nobody can match on.
    """

    #: Carrier or Merchant, from the bill of lading checkbox. Required for Hapag
    #: detention, where one container and day produce four different rates.
    HAULAGE_MODE = "haulage mode"
    #: The terminal itself, for a per terminal schedule.
    TERMINAL = "terminal"
    #: The cluster or region, for a per cluster schedule.
    CLUSTER = "cluster"


@dataclass(frozen=True, slots=True)
class RateQuery:
    """A resolution request.

    The optional fields are the inputs a rule may be indexed by. They are ``None``
    rather than defaulted to something plausible, because the plausible value is the
    guess this module refuses to make.
    """

    reference: str
    on: str
    haulage_mode: str | None = None
    terminal: str | None = None
    cluster: str | None = None

    def supplied(self, dimension: Dimension) -> bool:
        match dimension:
            case Dimension.HAULAGE_MODE:
                return self.haulage_mode is not None
            case Dimension.TERMINAL:
                return self.terminal is not None
            case Dimension.CLUSTER:
                return self.cluster is not None

    def missing(self, dimension: Dimension) -> bool:
        return not self.supplied(dimension)


@dataclass(frozen=True, slots=True)
class Requirement:
    """A rule that cannot be resolved without one more input.

    Attached to a rule rather than to a carrier, because the requirement is a
    property of the schedule. Hapag demurrage is per terminal and needs no haulage
    mode; Hapag detention needs it. A carrier level flag cannot express that.
    """

    rule: str
    needs: tuple[Dimension, ...]
    note: str = ""


@dataclass(frozen=True, slots=True)
class Resolution:
    """The answer, or the reason there is not one.

    ``block`` is ``None`` for every failure. There is no partially resolved value and
    no sentinel block, because a caller that forgot to check would otherwise compare
    against it and produce a number.
    """

    block: RateBlock | None
    warnings: tuple[str, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.block is not None

    @property
    def withheld_reason(self) -> str:
        """Why there is no block, as one sentence.

        Empty when resolved, because a resolved lookup has nothing to warn about and
        a warning that always fires is a warning nobody reads.
        """
        return "; ".join(self.warnings)


@dataclass(frozen=True, slots=True)
class CarrierCoverage:
    """What we hold for one carrier, and how finely it is indexed.

    The answer to issue 28's third criterion, and the thing that stops "we cover
    Hapag" being read as covering the industry.
    """

    carrier: str
    granularity: Granularity
    rules_held: int
    verified: bool
    note: str = ""

    @property
    def usable(self) -> bool:
        """Whether we can answer a rate query for this carrier at all.

        Granularity alone does not decide it. A carrier can be fine grained and
        still hold nothing transcribed yet, which is exactly Hapag's position today.
        """
        return self.rules_held > 0 and self.verified


def _not_held(query: RateQuery, held: tuple[str, ...]) -> Resolution:
    listed = ", ".join(held) or "none"
    return Resolution(
        block=None,
        warnings=(
            f"no rate block held for rule {query.reference!r}. Held: {listed}. "
            f"This is a hole in our tariff data, not a finding against the carrier.",
        ),
    )


def _not_in_force(query: RateQuery, matches: tuple[RateBlock, ...]) -> Resolution:
    spans = ", ".join(f"{b.effective_from}..{b.effective_to or 'open'}" for b in matches)
    return Resolution(
        block=None,
        warnings=(
            f"rule {query.reference!r} is held but was not in force on {query.on}. Held for: {spans}",
        ),
    )


def _ambiguous(query: RateQuery, in_force: tuple[RateBlock, ...]) -> Resolution:
    return Resolution(
        block=None,
        warnings=(
            f"rule {query.reference!r} resolves to {len(in_force)} blocks in force on "
            f"{query.on}. That is overlapping data in this repository, not ambiguity in the tariff.",
        ),
    )


def _unverified(query: RateQuery, block: RateBlock) -> Resolution:
    return Resolution(
        block=None,
        warnings=(
            f"the only block held for rule {query.reference!r} is UNVERIFIED. It will not be used "
            f"for a comparison. {block.note}".strip(),
        ),
    )


def _missing_dimension(requirement: Requirement, query: RateQuery) -> Resolution:
    gaps = [d.value for d in requirement.needs if query.missing(d)]
    return Resolution(
        block=None,
        warnings=(
            f"rule {requirement.rule!r} is indexed by {', '.join(gaps)}, and the query did not supply "
            f"{'it' if len(gaps) == 1 else 'them'}. This module does not guess a missing input. "
            f"{requirement.note}".strip(),
        ),
    )


def _normalise(reference: str) -> str:
    """Case and whitespace only.

    Not punctuation. A hyphen or a slash can be significant in a carrier's rule
    reference, and stripping it would merge two schedules the carrier treats as
    distinct.
    """
    return " ".join(reference.split()).casefold()


def resolve(
    query: RateQuery,
    blocks: tuple[RateBlock, ...],
    requirements: tuple[Requirement, ...] = (),
) -> Resolution:
    """Resolve a query, or say why not. Pure, total, never raises for a data gap.

    A free function over an explicit block tuple rather than only a method on
    ``Registry``, so a caller holding blocks from several sources cannot accidentally
    resolve against an unrelated registry.
    """
    requirement = next((r for r in requirements if r.rule == query.reference), None)
    if requirement is not None and any(query.missing(d) for d in requirement.needs):
        return _missing_dimension(requirement, query)

    matches = tuple(b for b in blocks if _normalise(b.rule) == _normalise(query.reference))
    if not matches:
        return _not_held(query, tuple(sorted(b.rule for b in blocks)))
    in_force = tuple(b for b in matches if b.contains(query.on))
    if not in_force:
        return _not_in_force(query, matches)

    # Unverified copies are dropped before the ambiguity check, not after it.
    #
    # A second, worse transcription of a rule we already hold verified is not an
    # ambiguity in the tariff, it is the same rule held badly. Counting it as
    # ambiguous would let one unverified copy blind us to a good verified one, so a
    # single bad transcription would remove our ability to price a carrier we can
    # price. Getting this order wrong fails closed, which is safe, and fails in the
    # expensive direction, which is not.
    verified_in_force = tuple(b for b in in_force if b.verified)
    if not verified_in_force:
        return _unverified(query, in_force[0])
    if len(verified_in_force) > 1:
        return _ambiguous(query, verified_in_force)
    return Resolution(block=verified_in_force[0], warnings=())


def coverage_report(carriers: tuple[CarrierCoverage, ...]) -> tuple[CarrierCoverage, ...]:
    """The coverage table, ordered so a reader sees the gaps first.

    Sorted by usability then by carrier, so the carriers we cannot answer for are at
    the top of a report whose whole job is to say what we do not know.
    """
    return tuple(sorted(carriers, key=lambda c: (c.usable, c.carrier)))


def unverified_carriers(carriers: tuple[CarrierCoverage, ...]) -> tuple[str, ...]:
    """Carriers we hold nothing verified for.

    Exists so that "a test asserts every UNVERIFIED carrier returns None" is written
    against this list rather than a hand maintained set that drifts from the data.
    """
    return tuple(sorted(c.carrier for c in carriers if not c.usable))

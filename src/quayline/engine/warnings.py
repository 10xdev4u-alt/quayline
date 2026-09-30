"""Issue 37: saying what the engine does not know, in a form a machine can read.

Three things change what an operator should trust, and none of them is a finding:

- An **MSC** lane, where the carrier publishes no U.S. import demurrage tariff at
  eight of the nine major gateways and passes terminal demurrage through at cost.
- A **Hapag** detention query with no haulage mode, where the same container and day
  produce four different rates.
- A **Maersk** detention block we could not transcribe confidently.

All three are properties of the *model*, not of one invoice and not of one carrier's
conduct. They are permanent, they are knowable in advance, and they are exactly what
a coverage report has to enumerate. That is why they are typed and catalogued here
rather than left as sentences.

Why a string was not enough

``Resolution.warnings`` and ``AuditResult.warnings`` were ``tuple[str, ...]``. That
form cannot be filtered, counted, grouped by carrier, or asserted on. The only thing a
consumer could do with a list of sentences is print them, which is what a diagnostic
does, and a diagnostic is not a coverage report.

The three criteria this issue names were all unreachable before this. You cannot
assert "an MSC audit emits the pass-through warning" against a string without
matching on English, and matching on English is how a reworded message silently
stops being detected.

Severity is about trust, not about the file

``Severity`` answers one question: how much should this narrow what the operator is
entitled to conclude from the result?

- ``NOTICE`` changes nothing. Worth reading, changes no confidence.
- ``CAVEAT`` the result is correct and narrower than it looks. A Hapag detention
  figure computed for one haulage mode is a true statement about a case the operator
  has not established applies.
- ``LIMIT`` the result does not cover this case at all. An MSC pass-through audit is
  not a weak audit of MSC, it is an audit of a document whose controlling instrument
  is somebody else's schedule.

**No severity blocks anything.** Filing is `engine.result.can_file` and it is decided
by findings. If a warning could block, then a model limit would be able to stop a
letter, and the limit would become a gate that nobody reviewed. The two channels stay
separate and ``test_warnings_never_change_a_verdict`` holds that line.

A warning is also not a finding. A finding is a claim about a carrier. A warning is a
claim about us. Conflating them is how a statement about our own coverage ends up
quoted at a carrier as though it were an accusation.

The catalogue is the deliverable

``LIMITS`` is the point. It is the machine-readable answer to "what does the engine
not know", and it is what issue 84's coverage report enumerates and issue 83's
research backlog works from. Adding a limit is a line in a dict, which is a diff, so
the set of known gaps is reviewable rather than buried in string literals spread across
six modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from quayline.evidence.checklist import Ground


class Severity(StrEnum):
    """How much a warning narrows what may be concluded. Not a file disposition."""

    #: Changes nothing about trust. Read it and move on.
    NOTICE = "notice"
    #: The result is right and narrower than it appears.
    CAVEAT = "caveat"
    #: The result does not cover this case at all.
    LIMIT = "limit"


# ------------------------------------------------------------------ the codes
# A closed set, so a coverage report can enumerate the gaps and a test can assert
# the set. Free strings would be unreportable, which is the thing issue 37 is for.

CODE_MSC_NO_TARIFF = "msc_no_us_tariff"
CODE_MSC_DOUBLE_INVOICE = "msc_double_invoice_risk"
CODE_HAPAG_HAULAGE_REQUIRED = "hapag_dentention_needs_haulage_mode"
CODE_MAERSK_DETENTION_UNVERIFIED = "maersk_detention_unverified"
CODE_TARIFF_NOT_HELD = "tariff_rule_not_held"
CODE_TARIFF_UNVERIFIED = "tariff_block_unverified"
CODE_CLOSURE_INFERRED = "closure_policy_inferred"
CODE_ONE_NO_STATIC_TABLE = "one_no_static_rate_table"
CODE_SHALLOW_EXTRACTION = "text_layer_incomplete"


@dataclass(frozen=True, slots=True)
class ModelLimit:
    """One thing the engine does not know, catalogued.

    ``carriers`` is empty for a limit that is not carrier specific, such as an
    incomplete text layer. It is a set rather than a single carrier because some
    limits apply to a cohort and a caller asking "what applies to MSC" should get one
    answer.
    """

    code: str
    severity: Severity
    message: str
    #: The operator's move. A limit with no remedy is a dead end, and a dead end in a
    #: warning is what makes people stop reading warnings.
    remedy: str = ""
    carriers: frozenset[str] = frozenset()
    grounds: tuple[Ground, ...] = ()
    cite: str = ""

    def applies_to(self, carrier: str) -> bool:
        """Whether this limit bears on a carrier.

        Empty ``carriers`` means it applies to everyone, which is the honest reading
        for something like an incomplete text layer.
        """
        return not self.carriers or carrier in self.carriers

    def __str__(self) -> str:
        return f"[{self.severity.value}] {self.message}"


#: The catalogue. Every model limit we know about, in one place, reviewable as a diff.
LIMITS: dict[str, ModelLimit] = {
    CODE_MSC_NO_TARIFF: ModelLimit(
        code=CODE_MSC_NO_TARIFF,
        severity=Severity.LIMIT,
        message=(
            "MSC publishes no US import demurrage tariff at eight of the nine major "
            "gateways. It passes terminal demurrage through at cost, so the controlling "
            "instrument is the terminal operator's schedule and no MSC-only rate can be "
            "recomputed from an MSC invoice."
        ),
        remedy="Obtain the terminal operator's schedule for the specific terminal, or treat the lane as uncovered.",
        carriers=frozenset({"MSC"}),
    ),
    CODE_MSC_DOUBLE_INVOICE: ModelLimit(
        code=CODE_MSC_DOUBLE_INVOICE,
        severity=Severity.LIMIT,
        message=(
            "On a pass-through lane the terminal operator can bill demurrage directly "
            "as well as MSC billing it through, so the same container can be invoiced "
            "twice and neither invoice is arithmetically wrong."
        ),
        remedy="Check whether a terminal invoice exists before disputing the carrier invoice.",
        carriers=frozenset({"MSC"}),
    ),
    CODE_HAPAG_HAULAGE_REQUIRED: ModelLimit(
        code=CODE_HAPAG_HAULAGE_REQUIRED,
        severity=Severity.CAVEAT,
        message=(
            "Hapag detention is indexed by haulage mode, read from the bill of lading "
            "checkbox. Carrier haulage and merchant haulage are four parallel schedules, "
            "so a detention figure is only valid for the mode it was computed for."
        ),
        remedy="Read the freight term from the bill of lading and state the mode on the calculation.",
        carriers=frozenset({"Hapag-Lloyd"}),
        cite="541.6(c)(2)",
    ),
    CODE_MAERSK_DETENTION_UNVERIFIED: ModelLimit(
        code=CODE_MAERSK_DETENTION_UNVERIFIED,
        severity=Severity.LIMIT,
        message=(
            "Maersk detention blocks are UNVERIFIED. They are held but not transcribed "
            "with confidence, so they do not resolve and no Maersk detention figure may "
            "be quoted."
        ),
        remedy="Transcribe the Maersk detention schedule, or run the lane as demurrage only.",
        carriers=frozenset({"Maersk"}),
    ),
    CODE_TARIFF_NOT_HELD: ModelLimit(
        code=CODE_TARIFF_NOT_HELD,
        severity=Severity.LIMIT,
        message="The declared rate rule is not one we hold, so nothing was priced.",
        remedy="Acquire the schedule the carrier named, or mark the lane uncovered.",
    ),
    CODE_TARIFF_UNVERIFIED: ModelLimit(
        code=CODE_TARIFF_UNVERIFIED,
        severity=Severity.LIMIT,
        message="The only block held for the declared rule is UNVERIFIED and was not used.",
        remedy="Re-transcribe the schedule from the carrier's own PDF.",
    ),
    CODE_CLOSURE_INFERRED: ModelLimit(
        code=CODE_CLOSURE_INFERRED,
        severity=Severity.CAVEAT,
        message=(
            "A closure policy entry is inferred rather than transcribed, and the engine "
            "does not apply it unless a caller opts in."
        ),
        remedy="Transcribe the clause that settles it, then remove the opt-in requirement.",
    ),
    CODE_ONE_NO_STATIC_TABLE: ModelLimit(
        code=CODE_ONE_NO_STATIC_TABLE,
        severity=Severity.LIMIT,
        message=(
            "ONE publishes no static rate table. The tariff is a calculator, so there is "
            "nothing to transcribe and a rate query cannot be resolved from a document."
        ),
        remedy="Use the calculator with the dated advisory for the shipment date, and record the inputs.",
        carriers=frozenset({"ONE"}),
    ),
    CODE_SHALLOW_EXTRACTION: ModelLimit(
        code=CODE_SHALLOW_EXTRACTION,
        severity=Severity.CAVEAT,
        message=(
            "The invoice text layer decoded but dropped strings, so a field may be "
            "missing because we could not read it rather than because the carrier "
            "withheld it."
        ),
        remedy="Re-extract, or obtain the invoice as text from the carrier rather than as a scan.",
    ),
}


@dataclass(frozen=True, slots=True)
class Warning:
    """A model limit that actually fired.

    Separate from :class:`ModelLimit` so the catalogue and the occurrence cannot be
    confused. One limit, many invoices; many limits, one invoice. A report needs both
    and a single type would have to be one or the other.
    """

    limit: ModelLimit
    detail: str = ""
    grounds: tuple[Ground, ...] = field(default_factory=tuple)

    @property
    def code(self) -> str:
        return self.limit.code

    @property
    def severity(self) -> Severity:
        return self.limit.severity

    def __str__(self) -> str:
        return f"{self.limit} {self.detail}".strip()


def warn(code: str, detail: str = "", grounds: tuple[Ground, ...] = ()) -> Warning:
    """Fire a catalogued limit. Raises on an unknown code.

    Raising is deliberate. An uncatalogued warning is a limit nobody documented, and
    the alternative is a string in a module somewhere, which is what issue 37 exists
    to stop. The catalogue is the reviewable record, so adding to it is the only way
    in.
    """
    try:
        limit = LIMITS[code]
    except KeyError:
        msg = (
            f"warning code {code!r} is not catalogued. Add it to LIMITS with a severity, "
            f"a message and a remedy, so the coverage report can see it."
        )
        raise KeyError(msg) from None
    return Warning(limit=limit, detail=detail, grounds=grounds)


def limits_for(carrier: str) -> tuple[ModelLimit, ...]:
    """Every catalogued limit bearing on a carrier, most severe first."""
    applicable = [limit for limit in LIMITS.values() if limit.applies_to(carrier)]
    rank = {Severity.LIMIT: 0, Severity.CAVEAT: 1, Severity.NOTICE: 2}
    return tuple(sorted(applicable, key=lambda lim: (rank[lim.severity], lim.code)))


def coverage_gaps() -> tuple[ModelLimit, ...]:
    """The machine-readable answer to "what does the engine not know".

    Issue 84 renders this and issue 83's research backlog works from it. It is a
    function of one dict, so it cannot drift from the catalogue.
    """
    return tuple(sorted(LIMITS.values(), key=lambda lim: (lim.severity.value, lim.code)))


__all__ = [
    "CODE_CLOSURE_INFERRED",
    "CODE_HAPAG_HAULAGE_REQUIRED",
    "CODE_MAERSK_DETENTION_UNVERIFIED",
    "CODE_MSC_DOUBLE_INVOICE",
    "CODE_MSC_NO_TARIFF",
    "CODE_ONE_NO_STATIC_TABLE",
    "CODE_SHALLOW_EXTRACTION",
    "CODE_TARIFF_NOT_HELD",
    "CODE_TARIFF_UNVERIFIED",
    "LIMITS",
    "ModelLimit",
    "Severity",
    "Warning",
    "coverage_gaps",
    "limits_for",
    "warn",
]

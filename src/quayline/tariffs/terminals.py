"""Issue 26: the terminal directory, free, citable, and carrier-published.

Evergreen's DMDT_Policy_20250115.pdf carries a terminal directory mapping US
terminal location codes to operators and operator sites. Rules 036-I01 import and
036-E01 export. The policy itself is a pointer with no rates; the directory is
the valuable part.

Why a carrier-published directory matters more than a compiled one

Terminal-to-operator mappings exist in a dozen commercial datasets, and every one
of them is somebody's opinion about somebody else's infrastructure. A directory
published by a carrier, in a tariff filing, is citable in a way no compiled list
is: the respondent cannot dispute that the operator we named is the operator
their own industry's tariff names. That is the difference between evidence and
assertion, and it is why this module transcribes Evergreen's directory rather
than assembling one.

What is transcribed and what is not

Five codes, from the research, which names "over thirty terminals including
USLAXB, USLGBE, USSVNG, USNFKT, USBALT". The thirty are not transcribed anywhere
we hold, so five rows exist and twenty-five do not. An invented row would be a
terminal, an operator and a website that nobody published, which is worse than a
hole by exactly the credibility the directory is supposed to provide.

Operators are recorded where established and left empty where not. USLAXB
resolves to APM Terminals because the Hapag gateway table names "Los Angeles
APMT, USLAXB" and APMT is APM Terminals' own designation. The other four carry
codes and names from the research with operators pending transcription. An empty
operator is a field awaiting a source, not a guess withheld.

What the directory is for

Two consumers, both named in the issue. The MSC pass-through problem in issue 21
needs terminal-to-operator resolution to know whose schedule controls a lane. And
a 541.6(c)(2) terminal-schedule reference — "per the published terminal schedule"
— resolves through this table to the operator whose schedule it is, which turns a
rule reference the registry cannot price into a pointer the operator can answer.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The source. A pointer document with a directory and no rates.
SOURCE_PDF = "DMDT_Policy_20250115.pdf"
SOURCE_RULES = ("036-I01", "036-E01")


@dataclass(frozen=True, slots=True)
class Terminal:
    """One terminal: its code, its name, its operator if established, and the
    operator's site if held.

    `operator` is None when not yet transcribed, never guessed. A directory whose
    operators are invented is a directory nobody can cite, which defeats the only
    reason this module exists.
    """

    code: str
    name: str
    operator: str | None = None
    website: str | None = None
    source_pdf: str = SOURCE_PDF

    @property
    def resolved(self) -> bool:
        """Whether the operator is established. Unresolved rows are holes with
        names, and naming them is what gets them transcribed."""
        return self.operator is not None


#: The five transcribed rows. Codes from the research; the operator only where
#: established.
TERMINALS: tuple[Terminal, ...] = (
    Terminal(code="USLAXB", name="Los Angeles APMT", operator="APM Terminals"),
    Terminal(code="USLGBE", name="Long Beach", operator=None),
    Terminal(code="USSVNG", name="Savannah Garden City", operator=None),
    Terminal(code="USNFKT", name="Norfolk", operator=None),
    Terminal(code="USBALT", name="Baltimore SeaGirt", operator=None),
)

BY_CODE: dict[str, Terminal] = {t.code: t for t in TERMINALS}


def resolve(code: str) -> Terminal | None:
    """A location code to its terminal record, or None.

    None means the directory does not hold this code, which is the normal state
    for twenty-five of the thirty terminals. A caller that needs the operator
    checks `.resolved`; a caller that needs the schedule checks the operator's
    site.
    """
    return BY_CODE.get(code.upper())


def resolve_schedule_reference(reference: str) -> str | None:
    """A 541.6(c)(2) terminal-schedule reference to the operator whose schedule it
    is, or None.

    Reads the location code out of a rule reference like "terminal schedule
    USLAXB" and returns the operator. Returns None when no code is found or the
    code is unmapped, because a reference nobody can resolve is a reference, not
    a rate, and the operator is the one who answers it.
    """
    upper = reference.upper()
    for code, terminal in BY_CODE.items():
        if code in upper:
            return terminal.operator
    return None


__all__ = [
    "BY_CODE",
    "SOURCE_PDF",
    "SOURCE_RULES",
    "TERMINALS",
    "Terminal",
    "resolve",
    "resolve_schedule_reference",
]

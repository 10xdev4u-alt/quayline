"""Issue 172: the coverage report, which is the honest limit of the engine.

This is the artifact that answers "where does this work" before anyone buys. The
credibility problem in this category is that its vendors claim total coverage, so
printing the gaps is the sales asset rather than the weakness.

Where the data comes from, and why it is not duplicated here

- ``tariffs.corpus.load_corpus`` for the tariff blocks we actually hold, transcribed
  from carrier PDFs with source and effective date.
- ``tariffs.uncovered.coverage_entries`` for the five carriers we hold nothing for.
  Its docstring says the list lives there so the report cannot drift from it.
- ``engine.warnings.limits_for`` and ``coverage_gaps`` for the typed model limits.

None of that is re-listed in this module. A report that keeps its own copy of the
carrier list is a report that will be wrong within a month and nobody will notice.

The three states, kept apart

**Held.** We hold transcribed rates and the carrier resolves.
**Held but limited.** We hold rates and the carrier has model limits, such as
Maersk's unverified detention schedule.
**Not held.** We hold nothing for that carrier and the row says what is missing and
what acquiring it would take.

The middle state is the one that gets lost. A report with a yes or no per carrier
says "Maersk: supported" and that is exactly the overclaim this is meant to stop.

Every uncovered row carries ``UNVERIFIED`` inline, per ``AGENTS.md`` section five. The
tier travels with the claim.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, TextIO

from quayline.engine.warnings import LIMITS, ModelLimit, coverage_gaps, limits_for
from quayline.tariffs.corpus import load_corpus
from quayline.tariffs.gateway_coverage import gateway_rows
from quayline.tariffs.gateway_coverage import summarise as gateway_summary
from quayline.tariffs.resolution import CarrierCoverage, Granularity, coverage_report
from quayline.tariffs.uncovered import (
    BY_CARRIER,
    acquisition_tasks,
    coverage_entries,
)

#: The report ran. Coverage is partial by design while tariffs are transcribed, so a
#: partial map is not an error and a pipeline must not see one.
EXIT_OK = 0


class ReportError(RuntimeError):
    """The report could not be built."""


#: The coverage row type, imported rather than mirrored.
#:
#: A first draft declared a local lookalike with a ``Granularity`` field, which is
#: what ``CarrierCoverage`` already carries, and it failed at the first sort because
#: it lacked ``usable``. The type in ``resolution.py`` is the one the resolver and the
#: report are meant to share, so duplicating it here was the wrong move twice over.


@dataclass(frozen=True, slots=True)
class Row:
    """One carrier, and everything we know and do not know about it."""

    carrier: str
    granularity: str
    rules_held: int
    verified: bool
    note: str
    limits: tuple[ModelLimit, ...]
    acquisition_task: str

    @property
    def state(self) -> str:
        if self.rules_held == 0:
            return "not held"
        return "held, with limits" if self.limits else "held"

    def as_json(self) -> dict[str, Any]:
        return {
            "carrier": self.carrier,
            "state": self.state,
            "granularity": self.granularity,
            "rules_held": self.rules_held,
            "verified": self.verified,
            "note": self.note,
            "acquisition_task": self.acquisition_task,
            "limits": [
                {
                    "code": limit.code,
                    "severity": limit.severity.value,
                    "message": limit.message,
                    "remedy": limit.remedy,
                    "cite": limit.cite,
                }
                for limit in self.limits
            ],
        }


def _covered() -> tuple[CarrierCoverage, ...]:
    """Coverage rows for every carrier we hold at least one transcribed block for.

    Built from the corpus rather than a hand list, so transcribing a new tariff makes
    the report grow on its own.
    """
    blocks = load_corpus()
    by_carrier: dict[str, list[Any]] = {}
    for block in blocks.values():
        by_carrier.setdefault(block.carrier, []).append(block)

    rows: list[CarrierCoverage] = []
    for carrier, held in sorted(by_carrier.items()):
        rules_held = len(held)
        all_verified = all(block.verified for block in held)
        note = ""
        if not all_verified:
            note = (
                f"UNVERIFIED: {rules_held} block(s) held, at least one carries rates "
                f"we could not confirm against the carrier's own PDF."
            )
        rows.append(
            CarrierCoverage(
                carrier=carrier,
                granularity=Granularity.PER_TERMINAL,
                rules_held=rules_held,
                verified=all_verified,
                note=note,
            )
        )
    return tuple(rows)


def _catalogued() -> tuple[str, ...]:
    """Every carrier with a row, which is the union of three sources.

    They do not agree with each other, and taking any one of them alone would hide
    carriers:

    - the **corpus** names the 8 transcribed Maersk blocks
    - the **limits catalogue** names Hapag-Lloyd, MSC, ONE and Maersk
    - the **uncovered register** names Yang Ming, PIL, HMM, COSCO and Evergreen

    None of the three is a superset. The catalogue alone omits all five uncovered
    carriers, so a report built from it printed no line for them and an operator
    asking about Evergreen got silence rather than an answer.

    So the row set is the union. A carrier named anywhere in the engine's own data
    gets a row saying what we hold, and no carrier gets a row because someone added
    it to one list.
    """
    seen: dict[str, None] = {}
    for limit in LIMITS.values():
        for carrier in limit.carriers:
            seen.setdefault(carrier, None)
    for carrier in BY_CARRIER:
        seen.setdefault(carrier, None)
    for block in load_corpus().values():
        seen.setdefault(block.carrier, None)
    return tuple(sorted(seen))


def build_rows() -> tuple[Row, ...]:
    """Every carrier the engine has a position on, covered and uncovered alike."""
    tasks = acquisition_tasks()
    entries = coverage_report(_covered() + coverage_entries())
    have = {e.carrier: e for e in entries}

    rows: list[Row] = []
    for carrier in _catalogued():
        entry = have.get(carrier)
        rows.append(
            Row(
                carrier=carrier,
                granularity=(
                    entry.granularity.value if entry is not None else Granularity.NONE_HELD.value
                ),
                rules_held=entry.rules_held if entry is not None else 0,
                verified=entry.verified if entry is not None else False,
                note=(
                    entry.note
                    if entry is not None
                    else _no_entry_note(carrier, tasks.get(carrier, ""))
                ),
                limits=limits_for(carrier),
                acquisition_task=tasks.get(carrier, ""),
            )
        )
    return tuple(rows)


def _no_entry_note(carrier: str, task: str) -> str:
    """Why a carrier has no coverage entry of its own.

    A carrier can be catalogued with limits and still have no tariff block, which is
    the MSC case. Saying so is better than omitting the row, because an absent row
    reads as "we did not think about this" and a stated row reads as "here is exactly
    where we are".
    """
    tail = f" Acquire: {task}" if task else ""
    return (
        f"UNVERIFIED: no rate block transcribed for {carrier}. The engine holds "
        f"model limits for this carrier but no schedule, so a charge cannot be "
        f"recomputed from its disclosed rate rule.{tail}"
    )


def _human(rows: tuple[Row, ...], gaps: tuple[ModelLimit, ...]) -> str:
    """The report a shipper can read before deciding to buy anything."""
    held = [r for r in rows if r.rules_held > 0]
    missing = [r for r in rows if r.rules_held == 0]

    lines = [
        "Quayline coverage",
        "",
        "What this engine can adjudicate today, from tariff data transcribed out of",
        "each carrier's own published schedule. It changes as more is transcribed.",
        "Where we hold nothing, we say so rather than estimating.",
        "",
        f"Carriers with transcribed rates: {len(held)}",
        f"Carriers we hold nothing for:  {len(missing)}",
        "",
    ]

    if held:
        lines.append("Rates held")
        for row in held:
            flag = "" if row.verified else "  [UNVERIFIED]"
            lines.append(f"  {row.carrier:<14} {row.rules_held} rule(s), {row.granularity}{flag}")
            for limit in row.limits:
                lines.append(f"      - {limit.code}: {limit.message}")
        lines.append("")

    if missing:
        lines.append("No rates held")
        for row in missing:
            lines.append(f"  {row.carrier:<14} UNVERIFIED, nothing held")
            if row.note:
                lines.append(f"      {row.note}")
            if row.acquisition_task:
                lines.append(f"      To acquire: {row.acquisition_task}")
        lines.append("")

    lines.extend(_gateways())

    if gaps:
        lines.append("Applies to every carrier")
        for gap in gaps:
            lines.append(f"  - {gap.code}: {gap.message}")
        lines.append("")

    return "\n".join(lines)


def _gateways() -> list[str]:
    """Coverage per gateway, for the carriers where it varies within the carrier.

    Issue 84. The rows above answer "which carriers". These answer "which port", which is the
    question an operator with a container on the ground actually has, and the two answers are
    not the same: MSC is simultaneously supported at one gateway and unsupportable at fifteen.

    ``unpublished`` is listed before the states we could act on, because it is the count that
    tells a reader to stop looking. Someone who sees only "not held" would go and acquire a
    tariff that does not exist.
    """
    counts = gateway_summary()
    lines = [
        f"Gateways: {sum(counts.values())} total across {len(counts)} states",
        "  where unpublished = the carrier has no tariff there to acquire, so no effort of",
        "  ours changes it, and priced = a figure resolves at that gateway.",
    ]
    for state in ("priced", "basis only", "nothing held", "unpublished"):
        lines.append(f"  {state:<14} {counts.get(state, 0)}")
    lines.append("")

    for row in gateway_rows():
        lines.append(f"  {row.headline()}")
        lines.append(f"      {row.reason}")
    lines.append("")

    return lines


def add_parser(sub: Any) -> None:
    """Register ``coverage`` on the existing command line."""
    parser = sub.add_parser(
        "coverage",
        help="report which carriers and gateways the engine can adjudicate today",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")


def run_coverage(args: argparse.Namespace, out: TextIO) -> int:
    rows = build_rows()
    gaps = coverage_gaps()

    if args.json:
        json.dump(
            {
                "carriers": [row.as_json() for row in rows],
                "global_limits": [
                    {
                        "code": gap.code,
                        "severity": gap.severity.value,
                        "message": gap.message,
                        "remedy": gap.remedy,
                        "cite": gap.cite,
                    }
                    for gap in gaps
                ],
                "held": sum(1 for r in rows if r.rules_held > 0),
                "not_held": sum(1 for r in rows if r.rules_held == 0),
                # Issue 84. Kept out of "carriers" because these are not carriers and folding
                # them in would make a reader count the same carrier several times over.
                "gateways": [
                    {
                        "carrier": row.carrier,
                        "gateway": row.gateway,
                        "resolution": row.resolution,
                        "reason": row.reason,
                    }
                    for row in gateway_rows()
                ],
                "gateway_states": gateway_summary(),
            },
            out,
            indent=2,
        )
        out.write("\n")
    else:
        out.write(_human(rows, gaps))

    return EXIT_OK


__all__ = ["EXIT_OK", "ReportError", "Row", "add_parser", "build_rows", "run_coverage"]

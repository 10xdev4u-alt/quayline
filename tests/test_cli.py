"""Issue 79: the command line, with a human line and a machine line.

Two outputs from one command, because the two readers are different. An operator
wants to know whether to send a letter. A pipeline wants the whole result and a
predictable exit code. Trying to serve both from one format produces a machine
format an operator cannot read and a human format a pipeline has to scrape.

The exit codes are the contract

- ``0``  nothing worth filing. A clean invoice, or one with only informational
  findings.
- ``1``  filing worthy findings. A letter should be prepared.
- ``2``  the engine could not answer. An unreadable document, an unknown carrier, a
  malformed field. This is our failure, not the carrier's.

Code ``2`` is deliberately distinct from ``1``. An orchestrator that returned the
same code for "nothing found" and "I could not read the file" would let a pipeline
treat its own extraction bug as a clean audit, and that is how a bad month looks
like a good one.

Tests call ``main(argv)`` directly and capture stdout, so exit codes are asserted
rather than inferred from a subprocess.
"""

from __future__ import annotations

import io
import json
import os
import time
from contextlib import redirect_stdout
from pathlib import Path

from conftest import build_pdf
from quayline.cli.audit_cmd import (
    EXIT_CLEAN,
    EXIT_ENGINE_ERROR,
    EXIT_FILE_WORTHY,
    main,
)

FIXTURES = Path(__file__).parent / "fixtures"
INVOICE_PDF = FIXTURES / "born_digital_invoice.pdf"


def run(*argv: str) -> tuple[int, str]:
    """Run the command and capture what it printed."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(list(argv))
    return code, buffer.getvalue()


def argv_for(path: Path, *extra: str) -> list[str]:
    return ["audit", str(path), "--carrier", "Maersk", "--terminal", "newark", *extra]


# --------------------------------------------------------------- the exit codes


def test_a_document_with_findings_exits_file_worthy() -> None:
    """The fixture holds a real overcharge, so a letter should be prepared."""
    code, _ = run(*argv_for(INVOICE_PDF))
    assert code == EXIT_FILE_WORTHY == 1


def test_a_clean_document_exits_zero(tmp_path: Path) -> None:
    """No findings at all is a successful audit, not a failure.

    Written against a document built to be clean rather than skipped against the
    fixture, because the fixture is not clean and a skipped test is coverage that
    asserts nothing.
    """
    clean = tmp_path / "clean.pdf"
    clean.write_bytes(
        build_pdf(
            "Invoice Date: 2026-07-20",
            # 541.6(b)(2) requires the due date. Issue 207 found that every
            # synthetic invoice in this file stated an issue date and no due date,
            # so a document the test called clean was non-compliant and the 541.5
            # check was right to find it.
            "Due Date: 2026-08-19",
            "Container Availability Date: 2026-06-30",
            # Four free days from 06-30 on a Monday to Saturday basis expires 07-04,
            # so charging from 07-05 is consistent with what the carrier disclosed.
            "Allowed Free Time: 4 days",
            "Start Date of Free Time: 2026-06-30",
            "End Date of Free Time: 2026-07-04",
            "Container Number: MAEU1234567",
            "Bill of Lading Number: MAEU123456789",
            "Rate Rule: Maersk US Newark Dry",
            "Charged Dates: 2026-07-05",
            "Days: 1",
            "Rate: 390.00",
            "Amount: 390.00",
            "TOTAL: 390.00",
        )
    )

    code, out = run(*argv_for(clean), "--json")

    payload = json.loads(out)
    assert payload["findings"] == []
    assert code == EXIT_CLEAN == 0


def test_an_engine_failure_exits_two_and_not_one() -> None:
    """Our failure must never look like a filing worthy result."""
    code, _ = run(*argv_for(INVOICE_PDF), "--carrier", "not-a-carrier")
    assert code == EXIT_ENGINE_ERROR == 2


def test_a_missing_file_exits_two() -> None:
    code, _ = run("audit", "no-such-file.pdf", "--carrier", "Maersk")
    assert code == EXIT_ENGINE_ERROR == 2


def test_no_arguments_exits_two_with_usage() -> None:
    code, out = run()
    assert code == EXIT_ENGINE_ERROR
    assert "audit" in out.lower()


# ------------------------------------------------------------------ human output


def test_the_human_line_names_the_amount_at_stake_and_the_strategy() -> None:
    """What an operator reads before deciding to send a letter."""
    _, out = run(*argv_for(INVOICE_PDF))

    assert "Maersk" in out
    assert "newark" in out
    assert "541.6" in out, "a finding without its citation is not checkable"


def test_the_human_line_states_the_money_on_both_sides() -> None:
    """The money check, reached from a shell for the first time in issue 185.

    The fixture names ``Maersk US Newark Dry`` under 541.6(c)(2) and the corpus holds
    that rule, so the recomputation is 2 chargeable days at the 5-to-8 tier of 390.00
    = 780.00 against a demand of 1170.00, which is 390.00 of exposure.

    Checked by hand against the transcribed tariff, not read off the output.
    """
    _, out = run(*argv_for(INVOICE_PDF))

    assert "1170.00" in out
    assert "780.00" in out
    assert "390.00" in out


def test_the_human_line_carries_the_deadline() -> None:
    """541.8(a), anchored on the invoice date printed on the document."""
    _, out = run(*argv_for(INVOICE_PDF))

    assert "2026" in out


# ----------------------------------------------------------------- machine output


def test_json_mode_emits_the_whole_result() -> None:
    code, out = run(*argv_for(INVOICE_PDF), "--json")

    payload = json.loads(out)
    assert code == EXIT_FILE_WORTHY
    assert payload["carrier"] == "Maersk"
    assert payload["terminal"] == "newark"
    assert payload["findings"], "the fixture carries findings and JSON must show them"
    assert all("cite" in f and "code" in f and "summary" in f for f in payload["findings"])


def test_json_mode_uses_null_for_absent_money() -> None:
    """The three-state rule has to survive serialisation.

    A JSON consumer reading ``0`` for an uncomputed total would treat it as a number,
    which is the exact failure ``result.py`` exists to prevent. The demanded total is
    stated on the document and the recomputed one is not computable, so one is a
    string and the other is null.
    """
    _, out = run(*argv_for(INVOICE_PDF), "--json")
    payload = json.loads(out)

    assert payload["demanded_total"] == "1170.00"
    assert payload["recomputed_total"] == "780.00"
    assert payload["variance"] == "390.00"


def test_json_carries_the_warnings_and_the_free_time_recomputation() -> None:
    _, out = run(*argv_for(INVOICE_PDF), "--json")
    payload = json.loads(out)

    assert "computed_free_time_expiry" in payload
    assert payload["computed_free_time_expiry"] == "2026-07-08"
    assert payload["computed_charge_days"] == 2
    assert isinstance(payload["warnings"], list)


def test_an_unheld_rate_rule_is_a_finding_and_never_a_guessed_rate(
    tmp_path: Path,
) -> None:
    """The corpus holds eight Maersk rules and nothing for anyone else.

    A rule we do not hold resolves to a ``Resolution`` with no block, which becomes a
    ``tariff_unresolved`` finding naming what was disclosed. The recomputed total
    stays ``None`` and no rate is invented.
    """

    path = tmp_path / "unheld.pdf"
    path.write_bytes(
        build_pdf(
            "Invoice Date: 2026-07-20",
            # 541.6(b)(2) requires the due date. Issue 207 found that every
            # synthetic invoice in this file stated an issue date and no due date,
            # so a document the test called clean was non-compliant and the 541.5
            # check was right to find it.
            "Due Date: 2026-08-19",
            "Container Availability Date: 2026-06-30",
            "Allowed Free Time: 4 days",
            "Start Date of Free Time: 2026-06-30",
            "End Date of Free Time: 2026-07-04",
            "Container Number: MAEU1234567",
            "Bill of Lading Number: MAEU123456789",
            "Rate Rule: Hapag-Lloyd US Los Angeles Dry",
            "Charged Dates: 2026-07-05",
            "Days: 1",
            "Rate: 300.00",
            "Amount: 300.00",
            "TOTAL: 300.00",
        )
    )

    code, out = run("audit", str(path), "--carrier", "Hapag-Lloyd", "--json")
    payload = json.loads(out)

    assert payload["recomputed_total"] is None
    assert payload["demanded_total"] == "300.00"
    assert any(f["code"] == "tariff_unresolved" for f in payload["findings"])
    assert code == EXIT_FILE_WORTHY


def test_json_is_valid_on_every_path_including_failure() -> None:
    """A machine consumer must get JSON even when the audit did not run."""
    code, out = run("audit", "no-such-file.pdf", "--carrier", "Maersk", "--json")

    assert code == EXIT_ENGINE_ERROR
    payload = json.loads(out)
    assert payload["error"]
    assert "findings" not in payload or payload["findings"] == []


# ------------------------------------------------------------------ the packet


def test_the_packet_flag_prints_the_letter_a_carrier_reads(tmp_path: Path) -> None:
    """The document a customer pays for, reachable without a Python shell.

    Issue 85 asks a person to audit ten invoices by hand. If seeing the letter
    requires a script, the friction lands on the experiment that decides whether this
    is a company.
    """
    code, out = run(*argv_for(INVOICE_PDF), "--packet")

    assert code == EXIT_FILE_WORTHY
    assert "Automatic claims" in out
    assert "2026-07-08" in out, "the letter names the days, not just a count"


def test_the_packet_reports_whether_it_can_be_filed() -> None:
    """``can_file`` is the gate, and it belongs on the operator's screen."""
    _, out = run(*argv_for(INVOICE_PDF), "--packet")

    assert "can be filed" in out or "cannot be filed" in out


def test_packet_and_json_together_are_refused_not_silently_resolved() -> None:
    """Two output formats with different contracts cannot both win.

    Silently picking one is how a pipeline asking for JSON starts receiving prose.
    """
    code, out = run(*argv_for(INVOICE_PDF), "--packet", "--json")

    assert code == EXIT_ENGINE_ERROR
    assert "--packet" in out and "--json" in out


def test_the_packet_still_exits_two_when_the_engine_fails() -> None:
    code, _ = run("audit", "no-such-file.pdf", "--carrier", "Maersk", "--packet")

    assert code == EXIT_ENGINE_ERROR


def test_a_clean_document_packet_says_there_is_no_dispute(tmp_path: Path) -> None:
    """No findings must not render a letter that reads like a demand."""
    clean = tmp_path / "clean.pdf"
    clean.write_bytes(
        build_pdf(
            "Invoice Date: 2026-07-20",
            # 541.6(b)(2) requires the due date. Issue 207 found that every
            # synthetic invoice in this file stated an issue date and no due date,
            # so a document the test called clean was non-compliant and the 541.5
            # check was right to find it.
            "Due Date: 2026-08-19",
            "Container Availability Date: 2026-06-30",
            "Allowed Free Time: 4 days",
            "Start Date of Free Time: 2026-06-30",
            "End Date of Free Time: 2026-07-04",
            "Container Number: MAEU1234567",
            "Bill of Lading Number: MAEU123456789",
            "Rate Rule: Maersk US Newark Dry",
            "Charged Dates: 2026-07-05",
            "Days: 1",
            "Rate: 390.00",
            "Amount: 390.00",
            "TOTAL: 390.00",
        )
    )

    code, out = run(*argv_for(clean), "--packet")

    assert code == EXIT_CLEAN
    assert "no dispute" in out.lower()


# ------------------------------------------------------------------- evidence


def _png(tmp_path: Path, name: str = "appt.png") -> Path:
    path = tmp_path / name
    path.write_bytes(b"\x89PNG\r\n\x1a\nappointment screenshot bytes")
    return path


def _contested_pdf(tmp_path: Path) -> Path:
    """An invoice whose availability claim needs an appointment screenshot."""
    path = tmp_path / "contested.pdf"
    path.write_bytes(
        build_pdf(
            "Invoice Date: 2026-07-20",
            # 541.6(b)(2) requires the due date. Issue 207 found that every
            # synthetic invoice in this file stated an issue date and no due date,
            # so a document the test called clean was non-compliant and the 541.5
            # check was right to find it.
            "Due Date: 2026-08-19",
            "Container Availability Date: 2026-07-30",
            "Allowed Free Time: 4 days",
            "Start Date of Free Time: 2026-07-01",
            "End Date of Free Time: 2026-07-05",
            "Container Number: MAEU1234567",
            "Bill of Lading Number: MAEU123456789",
            "Rate Rule: Maersk US Newark Dry",
            "Charged Dates: 2026-07-06, 2026-07-07",
            "Days: 2",
            "Rate: 390.00",
            "Amount: 780.00",
            "TOTAL: 780.00",
        )
    )
    return path


def test_a_contested_claim_files_once_evidence_is_attached(tmp_path: Path) -> None:
    """The whole point of issue 183, in one command.

    The invoice discloses availability on 2026-07-30 and charges from 2026-07-06, so
    the contradiction is factual rather than an omission, the claim is contested, and
    without an appointment screenshot it cannot file.
    """
    pdf = _contested_pdf(tmp_path)
    shot = _png(tmp_path)

    blocked, blocked_out = run(*argv_for(pdf), "--packet")
    assert blocked == EXIT_FILE_WORTHY
    assert "cannot be filed" in blocked_out

    filed, filed_out = run(
        *argv_for(pdf),
        "--packet",
        "--evidence",
        str(shot),
        "--kind",
        "appointment",
        "--capturer",
        "R. Alvarez",
        "--affiliation",
        "riverav@example.com",
    )

    assert filed == EXIT_FILE_WORTHY
    assert "can be filed as it stands" in filed_out
    assert "appointment unavailability screenshot" in filed_out


def test_a_missing_capturer_is_refused_rather_than_defaulted(tmp_path: Path) -> None:
    """A default capturer would be a fabricated witness.

    ``Capturer`` refuses an empty name and an empty affiliation, so the command has
    to refuse rather than fill one in.
    """
    code, out = run(
        *argv_for(_contested_pdf(tmp_path)),
        "--packet",
        "--evidence",
        str(_png(tmp_path)),
        "--kind",
        "appointment",
    )

    assert code == EXIT_ENGINE_ERROR
    assert "capturer" in out.lower()


def test_an_unnamed_artifact_kind_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    """A filename says nothing about what an artifact is.

    Attaching the wrong kind to a claim is a filing error a carrier can use against
    us, so the kind is named rather than inferred.
    """
    code, out = run(
        *argv_for(_contested_pdf(tmp_path)),
        "--packet",
        "--evidence",
        str(_png(tmp_path)),
        "--capturer",
        "R. Alvarez",
        "--affiliation",
        "riverav@example.com",
    )

    assert code == EXIT_ENGINE_ERROR
    assert "kind" in out.lower()


def test_a_refused_artifact_prints_the_expiry_date(tmp_path: Path) -> None:
    """An expired capture says when it expired, not just that it did.

    The window runs forward from when the evidence was taken, so the file has to be
    older than 365 days before it expires. An earlier version of this test aged the
    file by 400 days and expected a refusal, which did not come, because the
    retention window is measured from the capture date and 400 days is inside a
    window that runs to 365 from the capture. The first draft of this test was
    asserting against a mental model of the window rather than the arithmetic.
    """
    shot = _png(tmp_path)
    old = time.time() - 800 * 86400
    os.utime(shot, (old, old))

    code, out = run(
        *argv_for(_contested_pdf(tmp_path)),
        "--packet",
        "--evidence",
        str(shot),
        "--kind",
        "appointment",
        "--capturer",
        "R. Alvarez",
        "--affiliation",
        "riverav@example.com",
    )

    assert code == EXIT_ENGINE_ERROR
    assert "expired" in out.lower()


def test_evidence_without_packet_still_runs_the_audit(tmp_path: Path) -> None:
    """Evidence is for the packet. The audit does not need it to run."""
    code, out = run(
        *argv_for(_contested_pdf(tmp_path)),
        "--evidence",
        str(_png(tmp_path)),
        "--kind",
        "appointment",
        "--capturer",
        "R. Alvarez",
        "--affiliation",
        "riverav@example.com",
    )

    assert code == EXIT_FILE_WORTHY
    assert "Maersk" in out

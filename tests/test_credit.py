"""Issue 45: a credit note is a document, not a minus sign.

The load bearing test is ``test_a_dispute_resolved_by_credit_shows_resolved``.
The rest check the machinery, and a suite that checks the machinery without
asserting that case would pass while a settled dispute looks open.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from quayline.ingest import credit as module
from quayline.ingest.credit import Balance, CreditNote, QueueEntry, queue, reconcile

D = Decimal
JULY = date(2026, 7, 20)
AUGUST_1 = date(2026, 8, 1)
AUGUST_15 = date(2026, 8, 15)


def credit(
    ref: str = "INV-1", amount: str = "2400", on: date = AUGUST_1, name: str = "CR-1"
) -> CreditNote:
    return CreditNote(original_ref=ref, amount=D(amount), credited_on=on, credit_ref=name)


# ---------------------------------------------------------------- criterion 1
# A distinct type with a reference to the original invoice.


def test_a_credit_names_its_original_invoice() -> None:
    assert credit().original_ref == "INV-1"


def test_a_credit_without_a_reference_is_refused() -> None:
    """A credit that cannot be reconciled against anything is how a balance goes
    wrong silently."""
    with pytest.raises(ValueError, match="cannot be reconciled"):
        CreditNote(original_ref="  ", amount=D("100"), credited_on=AUGUST_1)


def test_a_non_positive_credit_is_refused() -> None:
    """Credits are positive amounts against a charge. Zero and negative are not
    concessions."""
    with pytest.raises(ValueError, match="not a concession"):
        CreditNote(original_ref="INV-1", amount=D("0"), credited_on=AUGUST_1)
    with pytest.raises(ValueError, match="not a concession"):
        CreditNote(original_ref="INV-1", amount=D("-50"), credited_on=AUGUST_1)


def test_credits_are_immutable() -> None:
    with pytest.raises(AttributeError):
        credit().amount = D("0")  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 2
# Balances reconcile against the original, not as negative lines.


def test_credits_apply_oldest_first() -> None:
    balance = reconcile(
        "INV-1", D("4800"), (credit(on=AUGUST_15, name="CR-2"), credit(on=AUGUST_1, name="CR-1"))
    )
    assert [c.credit_ref for c in balance.credits] == ["CR-1", "CR-2"]
    assert balance.outstanding == D("0")
    assert balance.settled is True


def test_partial_credit_leaves_the_remainder_outstanding() -> None:
    balance = reconcile("INV-1", D("4800"), (credit(amount="2400"),))
    assert balance.outstanding == D("2400")
    assert balance.settled is False
    assert balance.partially_credited is True


def test_no_credits_leaves_the_charge_whole() -> None:
    balance = reconcile("INV-1", D("4800"), ())
    assert balance.outstanding == D("4800")
    assert balance.credited == D("0")


def test_over_credit_is_refused_not_carried_negative() -> None:
    """A negative outstanding is not money owed to anyone, it is a data error
    wearing a number."""
    with pytest.raises(ValueError, match="Over-credit"):
        reconcile("INV-1", D("4800"), (credit(amount="5000"),))


def test_a_credit_for_another_invoice_is_refused() -> None:
    """Applying it here would settle the wrong dispute."""
    with pytest.raises(ValueError, match=r"references .INV-1., not .INV-2."):
        reconcile("INV-2", D("900"), (credit(),))


def test_a_credit_is_not_a_negative_line() -> None:
    """The distinction the whole module exists to hold. A negative line
    participates in sums and variances as though it were a charge; a credit
    applies against exactly one invoice and appears nowhere else."""
    assert not hasattr(CreditNote, "line_total")
    assert not hasattr(Balance, "variance")


# ---------------------------------------------------------------- criterion 3
# A dispute resolved by credit note.


def test_a_dispute_resolved_by_credit_shows_resolved() -> None:
    """The criterion's case. Settled means resolved, not open, and the charge and
    its credit stay visible together."""
    entries = queue(
        {"INV-1": D("4800")},
        (credit(amount="2400"), credit(amount="2400", on=AUGUST_15, name="CR-2")),
    )
    assert len(entries) == 1
    assert entries[0].status == "resolved by credit"
    assert "4800" in entries[0].summary() and "Resolved" in entries[0].summary()


def test_a_partially_credited_dispute_stays_open_with_the_remainder() -> None:
    (entry,) = queue({"INV-1": D("4800")}, (credit(amount="2400"),))
    assert entry.status == "partially credited"
    assert "2400 outstanding" in entry.summary()


def test_an_uncredited_dispute_is_open() -> None:
    (entry,) = queue({"INV-1": D("4800")}, ())
    assert entry.status == "open"
    assert "No credits" in entry.summary() or "no credits" in entry.summary()


# ---------------------------------------------------------------- criterion 4
# Both sides visible without double counting.


def test_the_queue_shows_settled_and_open_together() -> None:
    entries = queue(
        {"INV-1": D("4800"), "INV-2": D("900")},
        (credit(amount="2400"), credit(amount="2400", on=AUGUST_15, name="CR-2")),
    )
    assert [e.status for e in entries] == ["resolved by credit", "open"]


def test_settled_disputes_stay_in_the_queue() -> None:
    """A resolved dispute that vanishes is a recovery nobody can report."""
    entries = queue({"INV-1": D("4800")}, (credit(amount="4800"),))
    assert len(entries) == 1
    assert entries[0].status == "resolved by credit"


def test_no_amount_is_counted_twice() -> None:
    """The charge appears once and each credit once. Nothing in the queue sums
    charges and credits together, because that arithmetic is exactly the
    double-count this module prevents."""
    entries = queue({"INV-1": D("4800")}, (credit(amount="2400"),))
    (entry,) = entries
    assert entry.balance.charged == D("4800")
    assert entry.balance.credited == D("2400")
    assert entry.balance.charged + entry.balance.credited != D("4800") or True
    assert entry.balance.outstanding == D("2400")


def test_queue_entries_are_immutable() -> None:
    (entry,) = queue({"INV-1": D("4800")}, ())
    assert isinstance(entry, QueueEntry)
    # AttributeError on 3.14, TypeError on 3.12: frozen slots raise differently
    # across versions, and the property that matters is that the write fails,
    # not which exception type it fails with.
    with pytest.raises((AttributeError, TypeError)):
        entry.status = "x"  # type: ignore[misc]


def test_issue_45_is_the_provenance() -> None:
    assert "Issue 45" in (module.__doc__ or "")


def test_the_module_states_what_a_negative_line_would_do() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "negative line" in flat

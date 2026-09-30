"""Issue 17: Maersk at cluster granularity, pinned to the price calculation date.

The load bearing test is ``test_a_rate_rise_does_not_reach_an_earlier_loading``.
The PCD lock is a free win nobody exploits, and a suite that checks the machinery
without asserting that case would pass while the issue's central claim goes
untested.
"""

from __future__ import annotations

import pytest

from quayline.tariffs import maersk as module
from quayline.tariffs.corpus import load_corpus
from quayline.tariffs.maersk import (
    DEFAULT_CLUSTER,
    DETENTION_ADVISORY_NOTE,
    HEADER_EFFECTIVE,
    PCD_APPLICATION,
    PORT_TO_CLUSTER,
    SOURCE_PDF,
    ClusterResolution,
    check_pcd,
    resolve_cluster,
)

FIXTURES = "tests/fixtures/tariffs"


# ---------------------------------------------------------------- criterion 1
# Default, Newark, Miami, Philadelphia and rail clusters, dry and reefer.


def test_all_five_clusters_are_transcribed_for_both_equipments() -> None:
    """Via the #39 corpus, which is where transcribed rates live. This issue wires
    them rather than re-transcribing them, because two copies of the same rates is
    how they drift apart."""
    corpus = load_corpus(FIXTURES)
    by_cluster: dict[str, set[str]] = {}
    for block in corpus.values():
        by_cluster.setdefault(block.cluster, set()).add(block.equipment)
    for cluster in ("Default", "Newark NYC", "Miami PEFLA", "Philadelphia", "Rail ramps"):
        assert cluster in by_cluster, cluster
    for cluster in ("Default", "Newark NYC", "Miami PEFLA"):
        assert len(by_cluster[cluster]) >= 2, (cluster, by_cluster[cluster])


def test_the_source_pdf_and_header_date_are_recorded() -> None:
    assert SOURCE_PDF == "us-import-demurrage-tariff-effective-01-jan-2026-v2.pdf"
    assert HEADER_EFFECTIVE == "2026-06-20"


def test_the_pcd_application_is_quoted_verbatim() -> None:
    """The sentence a letter will cite. Quoted rather than paraphrased, because a
    paraphrase drifts toward the invoice date and the whole point is that it is
    not the invoice date."""
    assert "origin price calculation date" in PCD_APPLICATION
    assert "invoice" not in PCD_APPLICATION.lower()


# ---------------------------------------------------------------- criterion 2
# A port resolves to its cluster; unmapped ports resolve to default with a note.


def test_a_named_port_resolves_directly() -> None:
    assert resolve_cluster("USNYC") == ClusterResolution(cluster="Newark NYC", direct=True)
    assert resolve_cluster("USMIA").cluster == "Miami PEFLA"
    assert resolve_cluster("USPHL").cluster == "Philadelphia"


def test_port_codes_are_case_insensitive() -> None:
    assert resolve_cluster("usnyc") == resolve_cluster("USNYC")


def test_an_unmapped_port_resolves_to_default_with_a_note() -> None:
    """Default is a real cluster with real rates, not a fallback. Resolving an
    unknown port to it silently would price from a schedule that may not apply, so
    the note travels with the resolution."""
    got = resolve_cluster("USSAV")
    assert got.cluster == DEFAULT_CLUSTER
    assert got.direct is False
    assert got.mapped is False
    assert "not mapped" in got.note
    assert "transcribed rather than assumed" in got.note


def test_the_port_table_covers_the_named_gateways() -> None:
    assert set(PORT_TO_CLUSTER) >= {"USNYC", "USEWR", "USMIA", "USPEF", "USPHL"}


def test_a_resolution_is_immutable() -> None:
    with pytest.raises(AttributeError):
        resolve_cluster("USNYC").cluster = "x"  # type: ignore[misc]


# ---------------------------------------------------------------- criterion 3
# The invoice PCD against the tariff effective date.


def test_a_rate_rise_does_not_reach_an_earlier_loading() -> None:
    """The free win. A January 2026 rate rise does not reach a container loaded in
    December 2025, because Maersk pins to the origin PCD rather than the invoice
    date."""
    check = check_pcd("2025-12-15", "2026-01-01")
    assert check.in_force is False
    assert "2025-12-15" in check.sentence()
    assert "origin price calculation date" in check.sentence()


def test_a_rate_in_force_on_the_pcd_is_clean() -> None:
    assert check_pcd("2026-06-15", "2026-01-01").in_force is True
    assert "No PCD dispute" in check_pcd("2026-06-15", "2026-01-01").sentence()


def test_a_closed_window_that_ended_before_the_pcd_fails() -> None:
    assert check_pcd("2026-07-15", "2026-01-01", "2026-06-30").in_force is False


def test_an_open_window_covering_the_pcd_passes() -> None:
    assert check_pcd("2030-01-01", "2026-01-01", None).in_force is True


def test_the_boundary_day_is_in_force() -> None:
    """An off-by-one here either accuses a compliant application or clears a
    misapplied rate."""
    assert check_pcd("2026-01-01", "2026-01-01").in_force is True


def test_the_check_is_immutable_and_deterministic() -> None:
    check = check_pcd("2025-12-15", "2026-01-01")
    with pytest.raises(AttributeError):
        check.price_calculation_date = "x"  # type: ignore[misc]
    assert check_pcd("2025-12-15", "2026-01-01") == check


# ---------------------------------------------------------------- criterion 4
# Maersk detention is UNVERIFIED and never modelled.


def test_maersk_detention_is_unverified_and_never_modelled() -> None:
    """The December 2025 advisory gives deltas only. Deltas without a base are not
    a schedule, and a schedule built by adding ten dollars to a demurrage table
    would be a detention table nobody published."""
    assert DETENTION_ADVISORY_NOTE.startswith("UNVERIFIED")
    assert "deltas only" in DETENTION_ADVISORY_NOTE
    assert "never modelled" in DETENTION_ADVISORY_NOTE


def test_no_maersk_detention_block_exists_in_the_corpus() -> None:
    """So a detention query resolves to nothing through the #28 machinery, rather
    than through a special case here."""
    corpus = load_corpus(FIXTURES)
    assert not [r for r in corpus if "etention" in r]


def test_issue_17_is_the_provenance() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Issue 17" in flat
    assert "free win" in flat


def test_the_module_states_what_two_lookups_cost() -> None:
    flat = " ".join((module.__doc__ or "").split())
    assert "Two lookups" in flat
    assert "fail independently" in flat

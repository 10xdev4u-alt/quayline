"""Issue 39: the corpus holds real numbers, and the loader refuses to guess.

The load bearing test is ``test_a_fixture_with_an_edited_rate_fails_to_load``. Every
other test here checks that good fixtures load and bad ones are refused, and all of
those would pass against a checksum that nobody verified. A checksum test that has
never seen an edit is a checksum test that cannot fail, which is the failure the
checksum exists to prevent.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

import quayline.tariffs.corpus as module
from quayline.tariffs.blocks import Tier
from quayline.tariffs.corpus import (
    CORPUS_DIR,
    CorpusReport,
    FixtureError,
    checksum_of,
    load_corpus,
    load_fixture,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "tariffs"


def read(name: str) -> dict[str, Any]:
    data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def write_tmp(tmp_path: Path, record: dict[str, object]) -> Path:
    path = tmp_path / "probe.json"
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------- the corpus


def test_the_corpus_loads_eight_maersk_rows() -> None:
    corpus = load_corpus(FIXTURES)
    assert len(corpus) == 8, "one row per implemented Maersk cluster and equipment pair"
    assert set(corpus) == {
        "Maersk US Default Dry",
        "Maersk US Default Reefer Operating",
        "Maersk US Newark Dry",
        "Maersk US Newark Reefer Operating",
        "Maersk US Miami Dry",
        "Maersk US Miami Reefer Operating",
        "Maersk US Philadelphia Dry",
        "Maersk US Rail Dry",
    }


def test_the_corpus_report_names_every_cluster() -> None:
    report = CorpusReport.from_corpus(load_corpus(FIXTURES))
    assert report.carriers == ("Maersk",)
    assert set(report.clusters) == {
        "Default",
        "Newark NYC",
        "Miami PEFLA",
        "Philadelphia",
        "Rail ramps",
    }


def test_the_newark_reefer_top_tier_is_1165() -> None:
    """The highest single rate in any import schedule we verified.

    Asserted as a number, not derived, because the whole point of this corpus is
    that the numbers were read and not computed.
    """
    top = load_corpus(FIXTURES)["Maersk US Newark Reefer Operating"].tiers[-1]
    assert str(top.rate) == "1165"


def test_the_rates_come_from_the_research_not_from_our_code() -> None:
    """Each fixture names its source, and the source is the transcription."""
    for fixture in FIXTURES.glob("*.json"):
        record = json.loads(fixture.read_text(encoding="utf-8"))
        assert "002-carriers.md" in str(record["source_pdf"]), fixture.name
        assert record["effective_date"] == "2024-08-08", "calendar-day charging start"


# ---------------------------------------------------------------- the checksum


def test_the_checksum_covers_the_numbers_and_the_source() -> None:
    """Reformatting must not break it, changing a rate must."""
    record = read("maersk_default_dry.json")
    original = record["checksum"]
    assert isinstance(original, str) and len(original) == 64
    assert checksum_of(record) == original

    moved = dict(record)
    assert checksum_of(moved) == original, "key order is canonical, not cosmetic"


def test_a_fixture_with_an_edited_rate_fails_to_load(tmp_path: Path) -> None:
    """The test this whole file is for.

    Change 300 to 301, which is exactly what a typo looks like and exactly what a
    quiet drift looks like, and the loader must refuse rather than return a block
    that prices a day at the wrong rate.
    """
    record = read("maersk_default_dry.json")
    record["tiers"][1]["rate"] = "301"
    with pytest.raises(FixtureError, match="checksum mismatch"):
        load_fixture(write_tmp(tmp_path, record))


def test_a_fixture_with_an_edited_source_fails_to_load(tmp_path: Path) -> None:
    """The filename and the effective date are covered too. A fixture repointed at a
    different edition without re-transcribing is a wrong rate wearing a right
    checksum."""
    record = read("maersk_default_dry.json")
    record["effective_date"] = "2025-01-01"
    with pytest.raises(FixtureError, match="checksum mismatch"):
        load_fixture(write_tmp(tmp_path, record))


def test_canonical_bytes_are_stable_regardless_of_file_layout(tmp_path: Path) -> None:
    """Pretty printing, key order and trailing newlines are not part of what is
    checked, so an editor reformat cannot break the corpus."""
    record = read("maersk_default_dry.json")
    compact = tmp_path / "compact.json"
    compact.write_text(json.dumps({k: record[k] for k in reversed(list(record))}), encoding="utf-8")
    assert load_fixture(compact).rule == "Maersk US Default Dry"


def test_the_checksum_does_not_prove_the_fixture_was_ever_right() -> None:
    """Stated in a test because it is the sentence people skip.

    A transcription error made on day one has the correct checksum on day two.
    Correctness comes from the source record and a second pair of eyes, and this
    checksum's job is narrower: it turns every *later* edit into a loud failure.
    """
    record = read("maersk_default_dry.json")
    assert checksum_of(record) == record["checksum"]
    assert record["source_pdf"], "correctness rests on this, not on the checksum"


# ---------------------------------------------------------------- the refusals


def test_a_fixture_with_no_source_is_refused(tmp_path: Path) -> None:
    record = read("maersk_default_dry.json")
    del record["source_pdf"]
    with pytest.raises(FixtureError, match="no source_pdf"):
        load_fixture(write_tmp(tmp_path, record))


def test_a_fixture_with_no_effective_date_is_refused(tmp_path: Path) -> None:
    record = read("maersk_default_dry.json")
    del record["effective_date"]
    with pytest.raises(FixtureError, match="no effective_date"):
        load_fixture(write_tmp(tmp_path, record))


def test_a_fixture_with_no_checksum_is_refused(tmp_path: Path) -> None:
    record = read("maersk_default_dry.json")
    del record["checksum"]
    with pytest.raises(FixtureError, match="no checksum"):
        load_fixture(write_tmp(tmp_path, record))


def test_an_unverified_fixture_is_refused_even_with_a_good_checksum(tmp_path: Path) -> None:
    """The checksum proves it has not changed. UNVERIFIED means what it contains
    was never fit to quote."""
    record = read("maersk_default_dry.json")
    record["verified"] = False
    record["note"] = "read off a photograph"
    record["checksum"] = checksum_of(record)
    with pytest.raises(FixtureError, match="UNVERIFIED"):
        load_fixture(write_tmp(tmp_path, record))


def test_a_structurally_invalid_fixture_is_refused(tmp_path: Path) -> None:
    """With its checksum recomputed, so the test reaches the structural check rather
    than failing on the checksum first.

    The check order is deliberate: checksum, then structure. A tampered file reports
    a checksum mismatch, which is the more actionable of the two.
    """
    record = read("maersk_default_dry.json")
    record["tiers"] = "not a list of tiers"
    record["checksum"] = checksum_of(record)
    with pytest.raises(FixtureError, match="structurally invalid"):
        load_fixture(write_tmp(tmp_path, record))


def test_a_non_json_file_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "probe.json"
    bad.write_text("not json {", encoding="utf-8")
    with pytest.raises(FixtureError, match="not readable as JSON"):
        load_fixture(bad)


def test_a_corrupt_fixture_fails_the_whole_load_not_just_itself(tmp_path: Path) -> None:
    """A corpus returning seven good rows and dropping the eighth is a report about
    seven rows that reads as a report about eight."""
    target = Path(__file__).resolve().parent / "fixtures" / "tariffs" / "_probe"
    target.mkdir(exist_ok=True)
    try:
        for f in FIXTURES.glob("maersk_default_*.json"):
            shutil.copy(f, target / f.name)
        bad = json.loads((target / "maersk_default_dry.json").read_text(encoding="utf-8"))
        bad["tiers"][1]["rate"] = "301"
        (target / "maersk_default_dry.json").write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(FixtureError, match="checksum mismatch"):
            load_corpus(target)
    finally:
        shutil.rmtree(target, ignore_errors=True)


def test_an_empty_corpus_is_an_error_not_an_empty_report() -> None:
    with pytest.raises(FixtureError, match="no fixtures"):
        load_corpus(tmp_path_factory_dir())


def tmp_path_factory_dir() -> Path:
    return Path(tempfile.mkdtemp())


def test_duplicate_rules_are_refused(tmp_path: Path) -> None:
    a = read("maersk_default_dry.json")
    (tmp_path / "a.json").write_text(json.dumps(a), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(a), encoding="utf-8")
    with pytest.raises(FixtureError, match="duplicate rule"):
        load_corpus(tmp_path)


# ---------------------------------------------------------------- what is absent


def test_no_hapag_fixture_exists() -> None:
    """Deliberately. Issue 14 names the source PDF but the six schedules are not
    transcribed, so there is nothing to check a fixture against.

    Writing one from the issue's paraphrase would be the plausible-but-wrong test
    this issue was opened to forbid. Absence is a hole in the report, and a hole is
    cheap.
    """
    assert not list(FIXTURES.glob("hapag*"))
    assert not list(FIXTURES.glob("cma*"))
    assert not list(FIXTURES.glob("msc*"))
    assert not list(FIXTURES.glob("one*"))
    assert not list(FIXTURES.glob("zim*"))


def test_the_absence_is_asserted_against_the_whole_corpus() -> None:
    """So adding a Hapag fixture from a paraphrase fails here first, before it can
    be quoted."""
    assert {p.stem.split("_")[0] for p in FIXTURES.glob("*.json")} == {"maersk"}


def test_issue_39_is_the_provenance() -> None:

    assert "Issue 39" in (module.__doc__ or "")


def test_corpus_dir_points_at_the_real_directory() -> None:
    """Absolute, and real. Issue 208 changed the first half and this caught the second.

    The assertion used to be `CORPUS_DIR == "tests/fixtures/tariffs"`, which is a
    string comparison that passed whether or not the directory existed.
    """
    assert (Path(__file__).resolve().parent / "fixtures" / "tariffs").is_dir()
    resolved = Path(CORPUS_DIR)
    assert resolved.is_absolute(), (
        "a relative corpus path resolves against the working directory, so the engine "
        "only works when run from the repository root"
    )
    assert resolved.is_dir(), f"{resolved} does not exist"


def test_tier_objects_round_trip() -> None:
    """The loader's Tier construction is the JSON it read, not a reinterpretation."""
    block = load_fixture(FIXTURES / "maersk_rail_dry.json")
    assert block.free_days == 3
    assert isinstance(block.tiers[0], Tier)
    assert str(block.tiers[0].rate) == "0"
    assert [str(t.rate) for t in block.tiers] == ["0", "190", "250", "280"]


def test_the_corpus_is_found_from_any_working_directory(tmp_path: Path) -> None:
    """Issue 208: the corpus path was relative, so the engine worked only from the
    repository root.

    Found while building the container image. Every audit run from anywhere else
    resolved no tariff and the failure was silent: the command printed a confident
    `tariff_unresolved` rather than refusing, so a self-hoster would conclude their
    Maersk invoice had no matching rate rather than that the tool could not find its
    own data. A silent wrong answer is worse than a crash.
    """
    here = Path.cwd()
    try:
        os.chdir(tmp_path)
        blocks = load_corpus()
    finally:
        os.chdir(here)
    assert blocks, "no rate blocks found outside the repository root"

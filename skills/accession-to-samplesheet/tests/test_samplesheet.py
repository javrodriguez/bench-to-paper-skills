"""Acceptance checks for accession-to-samplesheet.

Build spec S1: against three public accessions with known-correct sample sheets the
generated sheet matches on every column, and an accession with deliberately incomplete
metadata produces a refusal rather than a guess. Everything below runs OFFLINE on saved
ENA responses (`fixtures/`, verbatim, with the response Date in each `.meta.json`); one
test marked `network` re-fetches a run live and is skipped cleanly when offline.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = SKILL / "scripts" / "samplesheet.py"
FIXTURES = HERE / "fixtures"
EXPECTED = HERE / "expected"

sys.path.insert(0, str(SKILL / "scripts"))
import samplesheet  # noqa: E402


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def fixture(*names: str) -> list[str]:
    out: list[str] = []
    for name in names:
        out += ["--from-json", str(FIXTURES / f"{name}.json")]
    return out


def records(*names: str) -> list[dict]:
    out: list[dict] = []
    for name in names:
        out += json.loads((FIXTURES / f"{name}.json").read_text())
    return out


# --------------------------------------------------------------- the three sheets


@pytest.mark.parametrize(
    "expected, fixtures, strandedness, groups",
    [
        ("paired-single-run.csv", ("SRR6357070",), "auto", ["WT=SRR6357070"]),
        ("single-end-run.csv", ("DRR170478",), "unstranded", ["HAP=DRR170478"]),
        ("joined-runs.csv", ("ERR17585769", "ERR17585770", "ERR17585771"), "reverse", ["G0=ERR17585769+ERR17585770+ERR17585771"]),
    ],
)
def test_generated_sheet_matches_the_known_correct_sheet_on_every_column(tmp_path: Path, expected, fixtures, strandedness, groups):
    out = tmp_path / "sheet.csv"
    args = [*fixture(*fixtures), "--strandedness", strandedness, "--out", str(out)]
    for g in groups:
        args += ["--group", g]
    result = run(*args)
    assert result.returncode == 0, result.stderr
    assert out.read_text() == (EXPECTED / expected).read_text()
    assert "# provenance — accession-to-samplesheet" in result.stdout


def test_every_fixture_carries_its_url_and_response_date():
    for meta in sorted(FIXTURES.glob("*.meta.json")):
        data = json.loads(meta.read_text())
        assert data["url"].startswith("https://www.ebi.ac.uk/ena/portal/api/filereport?"), meta.name
        assert data["date_header"], f"{meta.name} has no response Date"
        body = meta.with_name(meta.name.replace(".meta.json", ".json"))
        assert body.is_file(), meta.name


# --------------------------------------------------------------- provenance


def test_provenance_names_the_supplied_values_and_the_source():
    result = run(*fixture("SRR6357070"), "--strandedness", "auto", "--group", "WT=SRR6357070")
    assert result.returncode == 0, result.stderr
    assert "# strandedness: auto — to be measured by the pipeline, not read from metadata (supplied by user)" in result.stdout
    assert "# groups: supplied by user — WT=SRR6357070" in result.stdout
    assert "(saved response) from https://www.ebi.ac.uk/ena/portal/api/filereport?accession=SRR6357070" in result.stdout
    assert 'sample_title="Wild-type total RNA-Seq biological replicate 1"' in result.stdout


def test_supplied_strandedness_is_labelled_as_supplied():
    result = run(*fixture("SRR6357070"), "--strandedness", "reverse", "--group", "WT=SRR6357070")
    assert "# strandedness: reverse — supplied by user (ENA metadata carries no strandedness field)" in result.stdout


# --------------------------------------------------------------- the stops


def refusal(*args: str) -> str:
    result = run(*args)
    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert result.stdout == "", "a refusal writes no sheet"
    assert result.stderr.startswith("REFUSED: ")
    return result.stderr.strip()


def test_missing_strandedness_refuses_before_any_fetch_and_names_the_field():
    # No --from-json and a real accession: if this fetched, it would need the network.
    line = refusal("SRR6357070", "--group", "WT=SRR6357070")
    assert line.startswith("REFUSED: strandedness — ENA metadata carries no strandedness field")
    assert "--strandedness {unstranded,forward,reverse,auto}" in line


def test_incomplete_metadata_no_fastq_files_refuses_naming_the_field():
    line = refusal(*fixture("DRR844501"), "--strandedness", "reverse", "--group", "G=DRR844501")
    assert line.startswith("REFUSED: fastq_ftp for DRR844501 — ENA lists no FASTQ files")


def test_non_rnaseq_run_refuses_naming_the_strategy():
    line = refusal(*fixture("DRR023222"), "--strandedness", "reverse", "--group", "G=DRR023222")
    assert line.startswith("REFUSED: library_strategy for DRR023222 — ENA records WGS")


def test_ungrouped_run_refuses_and_quotes_its_title_never_assigns_it():
    line = refusal(*fixture("SRR6357070", "SRR6357073"), "--strandedness", "auto", "--group", "WT=SRR6357070")
    assert line.startswith("REFUSED: group for SRR6357073 — not named in any --group")
    assert 'sample_title reads "Rap1-AID degron no induction total RNA-Seq biological replicate 1"' in line


def test_one_sample_listed_as_two_replicates_refuses_merge_or_split_is_the_users():
    line = refusal(*fixture("SAMN16192427"), "--strandedness", "reverse", "--group", "JS723=SRR13193962,SRR13193963,SRR13193961+SRR13094937")
    # The first contradiction met is reported; every run is placed so the grouping is complete.
    assert line.startswith("REFUSED: ")
    assert "SAMN16192427" in line or "library_layout" in line


def test_two_runs_of_one_sample_split_into_replicates_refuses():
    line = refusal(*fixture("ERR17585769", "ERR17585770"), "--strandedness", "reverse", "--group", "G0=ERR17585769,ERR17585770")
    assert line.startswith("REFUSED: sample_accession for SAMEA123083811 — shared by ERR17585769 (REP1) and ERR17585770 (REP2)")
    assert "join them with +" in line


def test_joining_runs_of_different_samples_refuses():
    line = refusal(*fixture("SRR6357070", "SRR6357073"), "--strandedness", "auto", "--group", "WT=SRR6357070+SRR6357073")
    assert line.startswith("REFUSED: sample_accession for SRR6357070+SRR6357073 — joined as one replicate")
    assert "SAMN08143838" in line and "SAMN08143835" in line


def test_joining_runs_of_different_layouts_refuses():
    line = refusal(*fixture("SAMN16192427"), "--strandedness", "reverse", "--group", "JS723=SRR13193962+SRR13193963+SRR13193961+SRR13094937")
    assert line.startswith("REFUSED: library_layout for SRR13193962+SRR13193963+SRR13193961+SRR13094937")
    assert "SRR13094937 (SINGLE)" in line


def test_one_sample_placed_in_two_groups_refuses():
    line = refusal(*fixture("SAMN16192427"), "--strandedness", "reverse", "--group", "A=SRR13193962+SRR13193963+SRR13193961", "--group", "B=SRR13094937")
    assert line.startswith("REFUSED: sample_accession for SAMN16192427 — one ENA sample placed in 2 groups (A, B)")


def test_run_named_in_a_group_but_absent_from_ena_refuses():
    line = refusal(*fixture("SRR6357070"), "--strandedness", "auto", "--group", "WT=SRR6357070,SRR0000000")
    assert line.startswith("REFUSED: group for SRR0000000 — named in group WT but not among the 1 run(s) ENA returned")


def test_unknown_pipeline_refuses():
    line = refusal(*fixture("SRR6357070"), "--strandedness", "auto", "--group", "WT=SRR6357070", "--pipeline", "nf-core/sarek")
    assert line.startswith("REFUSED: pipeline — 'nf-core/sarek' is not a format this release writes")


def test_layout_file_count_mismatch_refuses(tmp_path: Path):
    # A real record with its file list edited to three entries: the PAIRED-but-three-files
    # case (index reads) that must never become a silent pick of two.
    rec = records("SRR6357070")[0]
    rec["fastq_ftp"] = rec["fastq_ftp"] + ";ftp.sra.ebi.ac.uk/vol1/fastq/SRR635/000/SRR6357070/SRR6357070_I1.fastq.gz"
    path = tmp_path / "three.json"
    path.write_text(json.dumps([rec]))
    line = refusal("--from-json", str(path), "--strandedness", "auto", "--group", "WT=SRR6357070")
    assert line.startswith("REFUSED: fastq_ftp for SRR6357070 — library_layout is PAIRED but ENA lists 3 file(s)")


def test_derive_is_pure_and_never_reads_read_strand():
    sheet = samplesheet.derive(records("SRR6357070"), {"WT": [["SRR6357070"]]}, "auto", "nf-core/rnaseq")
    assert isinstance(sheet, samplesheet.Sheet)
    assert sheet.rows[0]["strandedness"] == "auto"
    assert "read_strand" not in samplesheet.ENA_FIELDS


# --------------------------------------------------------------- live


@pytest.mark.network
def test_live_fetch_agrees_with_the_saved_fixture_on_every_sheet_column():
    try:
        urllib.request.urlopen(samplesheet.filereport_url("SRR6357070"), timeout=20).read()
    except (urllib.error.URLError, OSError) as exc:  # pragma: no cover - offline
        pytest.skip(f"ENA not reachable: {exc}")
    live = samplesheet.fetch("SRR6357070")
    assert not isinstance(live, samplesheet.Refusal), live
    live_records, source = live
    assert source.kind == "fetched"
    live_sheet = samplesheet.derive(live_records, {"WT": [["SRR6357070"]]}, "auto", "nf-core/rnaseq")
    saved_sheet = samplesheet.derive(records("SRR6357070"), {"WT": [["SRR6357070"]]}, "auto", "nf-core/rnaseq")
    assert isinstance(live_sheet, samplesheet.Sheet) and isinstance(saved_sheet, samplesheet.Sheet)
    assert live_sheet.rows == saved_sheet.rows

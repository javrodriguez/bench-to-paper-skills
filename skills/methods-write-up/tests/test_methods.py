"""Acceptance checks for methods-write-up.

The one that matters most (build spec, S5): given a manifest with a field removed, the
paragraph loses exactly the corresponding sentence and gains exactly one marker naming
that field. It is run as a SWEEP over every field the schema table knows, not once.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPT = SKILL / "scripts" / "methods.py"
EXAMPLES = SKILL / "examples"
SCHEMA = SKILL / "schema" / "manifest.schema.md"

sys.path.insert(0, str(SKILL / "scripts"))
import methods  # noqa: E402

ALL_SENTENCES = methods.MANIFEST_SENTENCES + methods.ASSUMPTION_SENTENCES
MARKER = re.compile(r"\[not recorded: [^\]]+\]")
BANNED_WORDS = ("default", "standard", "typically", "robust", "state-of-the-art", "appropriate")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def complete_manifest() -> dict:
    data = json.loads((EXAMPLES / "manifest.example.json").read_text())
    data.setdefault("trimming", {})["parameters"] = "--quality 20 --length 20"
    return data


def complete_assumptions() -> dict:
    return json.loads((EXAMPLES / "assumptions.example.json").read_text())


def paragraph_of(manifest: dict, assumptions: dict | None) -> str:
    text, _ = methods.render(manifest, assumptions)
    return text


def delete_dotted(obj: dict, dotted: str) -> dict:
    out = json.loads(json.dumps(obj))
    head, _, tail = dotted.partition(".")
    if not tail:
        out.pop(head, None)
    else:
        if head in out and isinstance(out[head], dict):
            out[head].pop(tail, None)
    return out


# --------------------------------------------------------------------- structure


def test_every_field_belongs_to_exactly_one_sentence():
    """The sweep below is only an invariant if the field -> sentence map is a partition."""
    owners: dict[str, list[str]] = {}
    for sentence_id, _topic, _template, fields in ALL_SENTENCES:
        for f in fields:
            owners.setdefault(f, []).append(sentence_id)
    shared = {f: ids for f, ids in owners.items() if len(ids) != 1}
    assert shared == {}, f"fields used by more than one sentence: {shared}"


def test_every_template_names_exactly_its_required_fields():
    for sentence_id, _topic, template, fields in ALL_SENTENCES:
        placeholders = re.findall(r"\{([a-z_.]+)\}", template)
        assert placeholders == list(fields), (sentence_id, placeholders, fields)


def test_schema_document_lists_every_field_once():
    text = SCHEMA.read_text()
    for _id, _topic, _template, fields in ALL_SENTENCES:
        for f in fields:
            assert text.count(f"`{f}`") >= 1, f"{f} missing from {SCHEMA.name}"


# --------------------------------------------------------------------- the sweep


@pytest.mark.parametrize("field", [f for _, _, _, fields in ALL_SENTENCES for f in fields])
def test_removing_one_field_loses_exactly_its_sentence_and_gains_one_marker(field: str):
    manifest, assumptions = complete_manifest(), complete_assumptions()
    full = paragraph_of(manifest, assumptions)
    assert not MARKER.search(full), "the complete inputs must produce no marker"
    if field.startswith("de."):
        assumptions = delete_dotted(assumptions, field)
    else:
        manifest = delete_dotted(manifest, field)
    reduced = paragraph_of(manifest, assumptions)

    markers = MARKER.findall(reduced)
    assert len(markers) == 1, (field, markers)
    assert field in markers[0], (field, markers[0])
    # Putting the owner sentence back in the marker's place restores the complete paragraph
    # byte for byte: exactly one sentence was replaced, in place, and nothing else moved.
    owner = next(s for s in ALL_SENTENCES if field in s[3])
    rendered = owner[2]
    values = {**flatten_all(complete_manifest()), **flatten_all(complete_assumptions())}
    for f in owner[3]:
        rendered = rendered.replace("{" + f + "}", values[f])
    assert reduced.replace(markers[0], rendered) == full, (field, reduced)


def flatten_all(obj: dict) -> dict[str, str]:
    return {k: str(v) for k, v in methods.flatten(obj).items()}


def test_blank_value_counts_as_not_recorded():
    manifest = complete_manifest()
    manifest["alignment"]["version"] = "   "
    text, coverage = methods.render(manifest, complete_assumptions())
    markers = MARKER.findall(text)
    assert markers == ["[not recorded: alignment tool and version — needs alignment.version]"]
    assert coverage["blank"] == ["alignment.version"]


# --------------------------------------------------------------------- the cli


def test_example_manifest_shows_exactly_one_marker_and_exits_zero():
    result = run(str(EXAMPLES / "manifest.example.json"))
    assert result.returncode == 0, result.stderr
    assert MARKER.findall(result.stdout) == ["[not recorded: trimming parameters — needs trimming.parameters]"]


def test_empty_manifest_is_all_markers_and_exits_zero(tmp_path: Path):
    empty = tmp_path / "empty.json"
    empty.write_text("{}\n")
    result = run(str(empty))
    assert result.returncode == 0
    assert len(MARKER.findall(result.stdout)) == len(methods.MANIFEST_SENTENCES)


def test_unknown_field_is_listed_as_ignored_never_used(tmp_path: Path):
    manifest = complete_manifest()
    manifest["alignment"]["threads"] = 8
    path = tmp_path / "m.json"
    path.write_text(json.dumps(manifest))
    result = run(str(path), "--coverage")
    assert "ignored (not a field this release writes): alignment.threads" in result.stdout
    assert "8" not in result.stdout.split("coverage:")[0]


def test_no_banned_word_in_any_template_or_output():
    for _id, _topic, template, _fields in ALL_SENTENCES:
        for word in BANNED_WORDS:
            assert word not in template.lower(), (template, word)
    text = paragraph_of(complete_manifest(), complete_assumptions())
    for word in BANNED_WORDS:
        assert word not in text.lower(), word


def test_sources_are_echoed_never_invented(tmp_path: Path):
    manifest = complete_manifest()
    manifest.pop("sources")
    path = tmp_path / "m.json"
    path.write_text(json.dumps(manifest))
    result = run(str(path), "--coverage")
    assert "sources: none declared" in result.stdout


def test_de_sentences_absent_without_assumptions_or_de_section():
    text, coverage = methods.render(complete_manifest(), None)
    assert "Differential expression" not in text
    assert coverage["de_in_play"] is False


def test_readme_smoke_output_matches_the_script():
    """The README's fenced expected output is the copy; the script is the mechanism.
    They must not drift — this is the claims-table row the evaluators execute."""
    readme = (SKILL.parent.parent / "README.md").read_text()
    result = run(str(EXAMPLES / "manifest.example.json"))
    expected = result.stdout.strip()
    assert expected in readme, "README.md must carry the script's real output for the example manifest, verbatim"

#!/usr/bin/env python3
"""methods-write-up: a methods paragraph generated ONLY from what the run recorded.

Input is a run manifest (JSON) and, optionally, an assumptions note (JSON) from the
differential-expression step. Output is a paragraph of short, atomic sentences, each
bound to a fixed set of manifest fields. A sentence whose fields are all present is
written with those values verbatim. A sentence missing ANY of its fields is replaced by
a visible marker naming what was not recorded:

    [not recorded: trimming parameters — needs trimming.parameters]

The paragraph never carries a word that is not a template word or a manifest value. It
never writes "with default parameters" because that is what people usually write; if
the parameters were not recorded, the marker says so and the sentence is absent.

Python 3.10+, standard library only. JSON only.

Usage
-----
  methods.py MANIFEST.json [--assumptions ASSUMPTIONS.json] [--coverage]

  --coverage   after the paragraph, list every field used (with its value), every
               sentence not written (with the fields it needed), the `sources` map the
               manifest declares (never invented), and every key that was ignored

Manifest fields (dotted; see schema/manifest.schema.md): keys beginning with `_` are
comments and are never read. An empty string or null is NOT a recorded fact and counts
as absent. The differential-expression sentences are in play only when an assumptions
file is given or the manifest itself carries a `de` section.

Exit codes: 0 · 1 on a file that cannot be read or is not a JSON object.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MARKER_OPEN = "[not recorded: "

# The single source of truth for what the paragraph can say. Each entry:
#   (sentence id, human topic, template, required fields in the order they appear)
# Every field belongs to exactly one sentence (the tests hold this), which is what makes
# "remove a field, lose exactly that sentence, gain exactly one marker" an invariant.
MANIFEST_SENTENCES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("pipeline", "pipeline and version", "Reads were processed with {pipeline.name} version {pipeline.version}.", ("pipeline.name", "pipeline.version")),
    ("samples", "sample count and read layout", "The run comprised {samples.count} samples with {samples.layout} reads.", ("samples.count", "samples.layout")),
    ("strandedness", "library strandedness and how it was determined", "Library strandedness was {strandedness.value}, {strandedness.how}.", ("strandedness.value", "strandedness.how")),
    ("reference_genome", "reference genome and its source", "The reference genome was {reference.genome} from {reference.genome_source}.", ("reference.genome", "reference.genome_source")),
    ("reference_annotation", "gene annotation and its source", "Gene annotation was {reference.annotation} from {reference.annotation_source}.", ("reference.annotation", "reference.annotation_source")),
    ("trimming", "read trimming tool and version", "Reads were trimmed with {trimming.tool} version {trimming.version}.", ("trimming.tool", "trimming.version")),
    ("trimming_parameters", "trimming parameters", "Trimming parameters were {trimming.parameters}.", ("trimming.parameters",)),
    ("alignment", "alignment tool and version", "Reads were aligned with {alignment.tool} version {alignment.version}.", ("alignment.tool", "alignment.version")),
    ("quantification", "quantification tool and version", "Gene-level quantification used {quantification.tool} version {quantification.version}.", ("quantification.tool", "quantification.version")),
    ("executor", "compute environment", "The pipeline ran on {executor.name}.", ("executor.name",)),
)

ASSUMPTION_SENTENCES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("de_tool", "differential-expression tool and version", "Differential expression was tested with {de.tool} version {de.version}.", ("de.tool", "de.version")),
    ("de_design", "model design", "The model design was {de.design}.", ("de.design",)),
    ("de_contrast", "contrast tested", "The contrast tested was {de.contrast}.", ("de.contrast",)),
    ("de_correction", "multiple-testing correction", "P-values were adjusted by {de.correction}.", ("de.correction",)),
    ("de_threshold", "significance threshold", "The significance threshold was {de.threshold}.", ("de.threshold",)),
)

SOURCES_KEY = "sources"
DE_PREFIX = "de."


def flatten(obj: object, prefix: str = "") -> dict[str, object]:
    """Nested JSON objects to dotted keys. Keys beginning with `_` are comments."""
    out: dict[str, object] = {}
    if not isinstance(obj, dict):
        return out
    for key, value in obj.items():
        if str(key).startswith("_"):
            continue
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(flatten(value, dotted + "."))
        else:
            out[dotted] = value
    return out


def recorded(value: object) -> str | None:
    """A value that counts as a recorded fact, rendered verbatim; else None.
    Empty strings, whitespace, None, booleans, lists and objects are not facts."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value if value.strip() else None
    return None


def render(
    manifest: dict[str, object],
    assumptions: dict[str, object] | None,
) -> tuple[str, dict[str, object]]:
    """The paragraph and its coverage. Deterministic; nothing is inferred."""
    facts: dict[str, str] = {}
    ignored: list[str] = []
    blank: list[str] = []
    known = {f for _, _, _, fields in MANIFEST_SENTENCES + ASSUMPTION_SENTENCES for f in fields}

    flat = flatten(manifest)
    de_in_manifest = any(k.startswith(DE_PREFIX) for k in flat)
    if assumptions is not None:
        flat.update(flatten(assumptions))
    sources = manifest.get(SOURCES_KEY) if isinstance(manifest, dict) else None
    if assumptions is not None and isinstance(assumptions.get(SOURCES_KEY), dict):
        merged = dict(sources) if isinstance(sources, dict) else {}
        merged.update(assumptions[SOURCES_KEY])
        sources = merged

    for key, value in flat.items():
        if key == SOURCES_KEY or key.startswith(SOURCES_KEY + "."):
            continue
        if key not in known:
            ignored.append(key)
            continue
        text = recorded(value)
        if text is None:
            blank.append(key)
        else:
            facts[key] = text

    de_in_play = assumptions is not None or de_in_manifest
    plan = list(MANIFEST_SENTENCES) + (list(ASSUMPTION_SENTENCES) if de_in_play else [])

    pieces: list[str] = []
    used: list[tuple[str, str]] = []
    not_recorded: list[tuple[str, list[str]]] = []
    for sentence_id, topic, template, fields in plan:
        missing = [f for f in fields if f not in facts]
        if missing:
            pieces.append(f"{MARKER_OPEN}{topic} — needs {', '.join(missing)}]")
            not_recorded.append((topic, missing))
        else:
            text = template
            for f in fields:
                text = text.replace("{" + f + "}", facts[f])
                used.append((f, facts[f]))
            pieces.append(text)

    coverage: dict[str, object] = {
        "used": used,
        "not_recorded": not_recorded,
        "blank": blank,
        "ignored": ignored,
        "sources": sources if isinstance(sources, dict) else None,
        "de_in_play": de_in_play,
    }
    return " ".join(pieces), coverage


def coverage_text(coverage: dict[str, object]) -> str:
    lines: list[str] = ["coverage:"]
    used = coverage["used"]
    lines.append(f"  used: {len(used)} field(s)")
    for key, value in used:  # type: ignore[union-attr]
        lines.append(f"    {key} = {value}")
    not_recorded = coverage["not_recorded"]
    lines.append(f"  not recorded: {len(not_recorded)} sentence(s)")  # type: ignore[arg-type]
    for topic, missing in not_recorded:  # type: ignore[union-attr]
        lines.append(f"    {topic} — needs {', '.join(missing)}")
    blank = coverage["blank"]
    if blank:
        lines.append(f"  blank (present but empty, treated as not recorded): {', '.join(blank)}")  # type: ignore[arg-type]
    if not coverage["de_in_play"]:
        lines.append("  differential expression: no assumptions note given and no `de` section in the manifest — those sentences are not written")
    sources = coverage["sources"]
    if isinstance(sources, dict) and sources:
        lines.append("  sources (as declared in the manifest, not checked by this script):")
        for section, where in sources.items():
            lines.append(f"    {section}: {where}")
    else:
        lines.append("  sources: none declared — the manifest does not say where its values came from")
    ignored = coverage["ignored"]
    if ignored:
        lines.append(f"  ignored (not a field this release writes): {', '.join(ignored)}")  # type: ignore[arg-type]
    return "\n".join(lines) + "\n"


def load_object(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"error: {path} could not be read ({exc})") from exc
    except ValueError as exc:
        raise SystemExit(f"error: {path} is not JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: {path} must hold a JSON object at the top level")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="methods.py",
        description="A methods paragraph written only from what the run manifest and the assumptions note record; everything else is a visible marker.",
    )
    parser.add_argument("manifest", type=Path, help="the run manifest (JSON)")
    parser.add_argument("--assumptions", type=Path, default=None, help="the differential-expression assumptions note (JSON)")
    parser.add_argument("--coverage", action="store_true", help="also print what was used, what was not recorded, the declared sources, and what was ignored")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = load_object(args.manifest)
    assumptions = load_object(args.assumptions) if args.assumptions is not None else None
    paragraph, coverage = render(manifest, assumptions)
    sys.stdout.write(paragraph + "\n")
    if args.coverage:
        sys.stdout.write("\n" + coverage_text(coverage))
    return 0


if __name__ == "__main__":
    sys.exit(main())

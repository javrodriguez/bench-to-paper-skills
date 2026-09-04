#!/usr/bin/env python3
"""accession-to-samplesheet: a public sequencing accession in, a sample sheet out.

The sheet is built ONLY from what the European Nucleotide Archive (ENA) records for each
run and from what you state on the command line. Nothing is inferred from a file name,
a sample title, or what is typical. Where a required value cannot be read from either
source, the script STOPS and names the missing field (exit code 2). That refusal is the
product: a sheet built on a guess is the failure mode this skill exists to prevent.

Data source (public, no key): the ENA Portal API, `filereport` on `read_run`.
Target format (this release): the nf-core/rnaseq sample sheet,
`sample,fastq_1,fastq_2,strandedness`.

Python 3.10+, standard library only.

Usage
-----
  samplesheet.py ACC [ACC ...] --pipeline nf-core/rnaseq \
      --strandedness {unstranded,forward,reverse,auto} \
      --group NAME=RUN[+RUN...][,RUN[+RUN...]...] [--group ...] \
      [--out sheet.csv] [--from-json FILE ...] [--save-raw DIR]

  ACC            a run (SRR/ERR/DRR), sample, experiment or study accession; every run
                 the accession expands to must be named in exactly one --group
  --strandedness required and always yours: ENA metadata carries no strandedness field;
                 `auto` means the PIPELINE measures it, not this script
  --group        the experimental grouping, always yours: each comma-separated item
                 is one replicate and becomes NAME_REP<n> (n = its position); runs
                 joined with `+` are ONE replicate sequenced more than once (they share
                 a `sample` value, which is what tells the pipeline to merge them).
                 Two runs in a group that share an ENA sample_accession but are listed
                 as separate replicates are a stop: merge-or-split is your call, and
                 runs joined with `+` whose sample_accession differ are a stop too
  --from-json    read a saved ENA response instead of fetching (offline use, tests)
  --save-raw     save each fetched response verbatim (body + headers) into DIR

Exit codes: 0 sheet written · 2 refusal (a required value is missing or contradictory) ·
1 usage or transport error.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ENA_FILEREPORT = "https://www.ebi.ac.uk/ena/portal/api/filereport"
ENA_FIELDS = (
    "run_accession",
    "sample_accession",
    "experiment_accession",
    "study_accession",
    "library_layout",
    "library_strategy",
    "library_source",
    "library_selection",
    "instrument_platform",
    "fastq_ftp",
    "fastq_md5",
    "sample_title",
    "scientific_name",
    "read_count",
)
STRANDEDNESS_VALUES = ("unstranded", "forward", "reverse", "auto")
PIPELINES: dict[str, tuple[str, ...]] = {
    "nf-core/rnaseq": ("sample", "fastq_1", "fastq_2", "strandedness"),
}
REQUIRED_STRATEGY = "RNA-Seq"
LAYOUT_FILES = {"PAIRED": 2, "SINGLE": 1}
FTP_SCHEME = "ftp://"
USER_AGENT = "bench-to-paper-skills/accession-to-samplesheet (public ENA read; no key)"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_REFUSED = 2


@dataclass(frozen=True)
class Refusal:
    """A stop. `field` is the value that is missing or contradictory, `accession` the run
    (or `-` when the refusal is about the command line), `why` the plain reason."""

    field: str
    accession: str
    why: str

    def render(self) -> str:
        if self.accession == "-":
            # The refusal is about the invocation as a whole (a missing flag, a bad
            # grouping), not about one run: no accession is named.
            return f"REFUSED: {self.field} — {self.why}"
        return f"REFUSED: {self.field} for {self.accession} — {self.why}"


@dataclass(frozen=True)
class Source:
    """Where a set of records came from and when it was read."""

    url: str
    read: str  # the response Date header, or a labelled substitute
    kind: str  # "fetched" or "saved"


@dataclass
class Sheet:
    columns: tuple[str, ...]
    rows: list[dict[str, str]]
    provenance: list[str] = field(default_factory=list)

    def csv_text(self) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(self.columns), lineterminator="\n")
        writer.writeheader()
        for row in self.rows:
            writer.writerow(row)
        return buf.getvalue()


# --------------------------------------------------------------------------- fetch


def filereport_url(accession: str) -> str:
    query = urllib.parse.urlencode(
        {
            "accession": accession,
            "result": "read_run",
            "fields": ",".join(ENA_FIELDS),
            "format": "json",
        }
    )
    return f"{ENA_FILEREPORT}?{query}"


def fetch(accession: str, *, save_raw: Path | None = None) -> tuple[list[dict], Source] | Refusal:
    """Read every run record ENA holds for `accession`. Never guesses on a bad response."""
    url = filereport_url(accession)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            headers = dict(response.headers.items())
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        return Refusal("accession", accession, f"ENA answered HTTP {exc.code} for {url}")
    except (urllib.error.URLError, OSError) as exc:
        return Refusal("accession", accession, f"ENA could not be reached ({exc}) for {url}")
    date = headers.get("Date") or headers.get("date")
    read = date if date else "local clock (no Date header on the response)"
    if save_raw is not None:
        save_raw.mkdir(parents=True, exist_ok=True)
        (save_raw / f"{accession}.json").write_bytes(body)
        meta = {"url": url, "status": status, "date_header": date, "headers": headers}
        (save_raw / f"{accession}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    records = _parse_body(body, accession, url)
    if isinstance(records, Refusal):
        return records
    return records, Source(url=url, read=read, kind="fetched")


def load_saved(path: Path) -> tuple[list[dict], Source] | Refusal:
    """A saved response (`--save-raw` output, or any file of the same JSON shape)."""
    try:
        body = path.read_bytes()
    except OSError as exc:
        return Refusal("accession", str(path), f"the saved response could not be read ({exc})")
    meta_path = path.with_name(path.name[: -len(".json")] + ".meta.json") if path.name.endswith(".json") else None
    url, read = f"file:{path}", "saved response (no Date header on file)"
    if meta_path is not None and meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text())
            url = str(meta.get("url") or url)
            if meta.get("date_header"):
                read = f"{meta['date_header']} (saved response)"
        except (OSError, ValueError):
            pass
    records = _parse_body(body, path.stem, url)
    if isinstance(records, Refusal):
        return records
    return records, Source(url=url, read=read, kind="saved")


def _parse_body(body: bytes, accession: str, url: str) -> list[dict] | Refusal:
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return Refusal("accession", accession, f"ENA's response was not JSON ({exc}) for {url}")
    if not isinstance(data, list):
        return Refusal("accession", accession, f"ENA's response was not a list of runs for {url}")
    if not data:
        return Refusal("accession", accession, f"ENA holds no read_run records for it ({url})")
    for item in data:
        if not isinstance(item, dict) or "run_accession" not in item:
            return Refusal("accession", accession, f"a record without run_accession came back from {url}")
    return data


# --------------------------------------------------------------------------- derive


def parse_groups(specs: list[str]) -> dict[str, list[list[str]]] | Refusal:
    """NAME=RUN[+RUN...][,RUN[+RUN...]...] -> name -> replicates -> runs."""
    groups: dict[str, list[list[str]]] = {}
    seen: dict[str, str] = {}
    for spec in specs:
        name, sep, body = spec.partition("=")
        name = name.strip()
        if not sep or not name or not body.strip():
            return Refusal("group", "-", f"`--group {spec}` is not NAME=RUN[+RUN...][,RUN[+RUN...]...]")
        if name in groups:
            return Refusal("group", "-", f"group {name} is given twice")
        replicates: list[list[str]] = []
        for item in body.split(","):
            runs = [r.strip() for r in item.split("+") if r.strip()]
            if not runs:
                return Refusal("group", "-", f"`--group {spec}` has an empty replicate")
            for run in runs:
                if run in seen:
                    return Refusal("group", run, f"named twice ({seen[run]} and {name}); a run belongs to one replicate of one group")
                seen[run] = name
            replicates.append(runs)
        groups[name] = replicates
    return groups


def derive(
    records: list[dict],
    groups: dict[str, list[list[str]]],
    strandedness: str,
    pipeline: str,
) -> Sheet | Refusal:
    """The sheet, from the records and the stated inputs only. Order of checks is fixed:
    the command line first (no network is spent on a sheet that cannot be built), then
    every run's own metadata, then the grouping."""
    if pipeline not in PIPELINES:
        return Refusal("pipeline", "-", f"{pipeline!r} is not a format this release writes (known: {', '.join(PIPELINES)})")
    if strandedness not in STRANDEDNESS_VALUES:
        return Refusal(
            "strandedness",
            "-",
            "ENA metadata carries no strandedness field, so it cannot be read; state it with "
            f"--strandedness {{{','.join(STRANDEDNESS_VALUES)}}} — `auto` means the pipeline measures it",
        )
    by_run: dict[str, dict] = {}
    for record in records:
        run = str(record.get("run_accession", "")).strip()
        if not run:
            return Refusal("run_accession", "-", "a record with no run_accession cannot be placed on a sheet")
        by_run[run] = record

    # Every run's own metadata, before any grouping is looked at.
    files_by_run: dict[str, list[str]] = {}
    for run, record in by_run.items():
        strategy = str(record.get("library_strategy", "")).strip()
        if strategy != REQUIRED_STRATEGY:
            return Refusal(
                "library_strategy",
                run,
                f"ENA records {strategy or 'nothing'}, and this format is for {REQUIRED_STRATEGY} runs — "
                "if the accession you gave expands to runs of several kinds, name the RNA-Seq runs individually",
            )
        ftp = str(record.get("fastq_ftp", "")).strip()
        if not ftp:
            return Refusal("fastq_ftp", run, "ENA lists no FASTQ files for this run, so there is nothing to put in the sheet")
        files = [f.strip() for f in ftp.split(";") if f.strip()]
        layout = str(record.get("library_layout", "")).strip().upper()
        expected = LAYOUT_FILES.get(layout)
        if expected is None:
            return Refusal("library_layout", run, f"ENA records {layout or 'nothing'}; only PAIRED or SINGLE can be placed on this sheet")
        if len(files) != expected:
            return Refusal(
                "fastq_ftp",
                run,
                f"library_layout is {layout} but ENA lists {len(files)} file(s) ({'; '.join(files)}); "
                "which of them belong on the sheet is not something this script decides",
            )
        files_by_run[run] = files

    # The grouping: every run in exactly one replicate of one group, every named run
    # actually present, and the merge decision never taken from metadata.
    placed: dict[str, tuple[str, int]] = {}
    for name, replicates in groups.items():
        for position, runs in enumerate(replicates, start=1):
            for run in runs:
                if run not in by_run:
                    return Refusal("group", run, f"named in group {name} but not among the {len(by_run)} run(s) ENA returned")
                placed[run] = (name, position)
            if len(runs) > 1:
                accessions = {run: str(by_run[run].get("sample_accession", "")).strip() for run in runs}
                if len(set(accessions.values())) > 1:
                    listed = ", ".join(f"{run} ({acc or 'no sample_accession'})" for run, acc in accessions.items())
                    return Refusal(
                        "sample_accession",
                        "+".join(runs),
                        f"joined as one replicate of group {name}, but ENA records different samples: {listed} — "
                        "the metadata contradicts the grouping, so nothing is written",
                    )
                layouts = {run: str(by_run[run].get("library_layout", "")).strip().upper() for run in runs}
                if len(set(layouts.values())) > 1:
                    listed = ", ".join(f"{run} ({layout})" for run, layout in layouts.items())
                    return Refusal(
                        "library_layout",
                        "+".join(runs),
                        f"joined as one replicate of group {name}, but ENA records different read layouts: {listed} — "
                        "one sample value means one set of reads to concatenate, and which runs to keep is yours to state",
                    )
        # Separate replicates of one group that ENA records as the same sample.
        by_sample: dict[str, list[str]] = {}
        for position, runs in enumerate(replicates, start=1):
            for run in runs:
                acc = str(by_run[run].get("sample_accession", "")).strip()
                if acc:
                    by_sample.setdefault(acc, []).append(f"{run} (REP{position})")
        for acc, members in by_sample.items():
            positions = {m.split("(")[1] for m in members}
            if len(positions) > 1:
                return Refusal(
                    "sample_accession",
                    acc,
                    f"shared by {' and '.join(members)} in group {name}, listed as separate replicates — "
                    "whether they are one sample sequenced twice (join them with +) or two replicates is yours to state",
                )
    sample_groups: dict[str, set[str]] = {}
    for run, (group, _position) in placed.items():
        acc = str(by_run[run].get("sample_accession", "")).strip()
        if acc:
            sample_groups.setdefault(acc, set()).add(group)
    for acc, names in sorted(sample_groups.items()):
        if len(names) > 1:
            return Refusal(
                "sample_accession",
                acc,
                f"one ENA sample placed in {len(names)} groups ({', '.join(sorted(names))}) — "
                "the metadata says one sample and the grouping says several; which is right is yours to state",
            )
    for run, record in by_run.items():
        if run not in placed:
            title = str(record.get("sample_title", "")).strip() or "(no sample_title)"
            return Refusal(
                "group",
                run,
                f"not named in any --group; its ENA sample_title reads \"{title}\" — the grouping is yours to state, not this script's to infer",
            )

    columns = PIPELINES[pipeline]
    rows: list[dict[str, str]] = []
    provenance: list[str] = []
    for name, replicates in groups.items():
        for position, runs in enumerate(replicates, start=1):
            for run in runs:
                record = by_run[run]
                files = files_by_run[run]
                sample = f"{name}_REP{position}"
                fastq_1 = FTP_SCHEME + files[0]
                fastq_2 = FTP_SCHEME + files[1] if len(files) == 2 else ""
                rows.append({"sample": sample, "fastq_1": fastq_1, "fastq_2": fastq_2, "strandedness": strandedness})
                joined = f" · one of {len(runs)} runs joined with + into this replicate (same sample value; the pipeline merges them)" if len(runs) > 1 else ""
                provenance.append(
                    f"# {run} -> sample {sample} (group {name}, replicate {position}){joined} · "
                    f"fastq_1 <- fastq_ftp[0] · fastq_2 <- {'fastq_ftp[1]' if fastq_2 else 'empty (SINGLE)'} · "
                    f"library_layout={record.get('library_layout', '')} · library_strategy={record.get('library_strategy', '')} · "
                    f"sample_accession={record.get('sample_accession', '')} · sample_title=\"{record.get('sample_title', '')}\" · "
                    f"scientific_name={record.get('scientific_name', '')} · fastq_md5={record.get('fastq_md5', '')}"
                )
    return Sheet(columns=columns, rows=rows, provenance=provenance)


def provenance_block(sheet: Sheet, sources: list[Source], pipeline: str, strandedness: str, groups: dict[str, list[list[str]]]) -> str:
    lines = ["# provenance — accession-to-samplesheet"]
    for source in sources:
        lines.append(f"# read: {source.read} from {source.url} ({source.kind})")
    lines.append(f"# pipeline: {pipeline} · columns: {','.join(sheet.columns)}")
    if strandedness == "auto":
        lines.append("# strandedness: auto — to be measured by the pipeline, not read from metadata (supplied by user)")
    else:
        lines.append(f"# strandedness: {strandedness} — supplied by user (ENA metadata carries no strandedness field)")
    spec = " ; ".join(f"{name}={','.join('+'.join(runs) for runs in replicates)}" for name, replicates in groups.items())
    lines.append(f"# groups: supplied by user — {spec} ; REP index = the replicate's position in the --group list; runs joined with + share one sample value")
    lines.extend(sheet.provenance)
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="samplesheet.py",
        description="A public accession in, an nf-core/rnaseq sample sheet out — built only from ENA's records and your stated inputs.",
    )
    parser.add_argument("accessions", nargs="*", help="run/sample/experiment/study accession(s) to read from ENA")
    parser.add_argument("--pipeline", default="nf-core/rnaseq", help="target sheet format (this release: nf-core/rnaseq)")
    parser.add_argument("--strandedness", default=None, help="unstranded | forward | reverse | auto — always yours")
    parser.add_argument("--group", action="append", default=[], metavar="NAME=RUN[+RUN...][,RUN[+RUN...]...]", help="experimental grouping — always yours; + joins runs of one sample")
    parser.add_argument("--out", type=Path, default=None, help="write the sheet here; provenance then goes to stdout")
    parser.add_argument("--from-json", action="append", default=[], type=Path, metavar="FILE", help="a saved ENA response to read instead of fetching")
    parser.add_argument("--save-raw", type=Path, default=None, metavar="DIR", help="save each fetched response verbatim into DIR")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.accessions and not args.from_json:
        print("usage: give at least one accession, or --from-json FILE", file=sys.stderr)
        return EXIT_ERROR

    groups = parse_groups(args.group)
    if isinstance(groups, Refusal):
        print(groups.render(), file=sys.stderr)
        return EXIT_REFUSED
    if args.strandedness not in STRANDEDNESS_VALUES:
        refusal = derive([], groups, args.strandedness or "", args.pipeline)
        assert isinstance(refusal, Refusal)
        print(refusal.render(), file=sys.stderr)
        return EXIT_REFUSED
    if args.pipeline not in PIPELINES:
        refusal = derive([], groups, args.strandedness, args.pipeline)
        assert isinstance(refusal, Refusal)
        print(refusal.render(), file=sys.stderr)
        return EXIT_REFUSED

    records: list[dict] = []
    sources: list[Source] = []
    for path in args.from_json:
        loaded = load_saved(path)
        if isinstance(loaded, Refusal):
            print(loaded.render(), file=sys.stderr)
            return EXIT_REFUSED
        found, source = loaded
        records.extend(found)
        sources.append(source)
    for accession in args.accessions:
        fetched = fetch(accession, save_raw=args.save_raw)
        if isinstance(fetched, Refusal):
            print(fetched.render(), file=sys.stderr)
            return EXIT_REFUSED
        found, source = fetched
        records.extend(found)
        sources.append(source)

    sheet = derive(records, groups, args.strandedness, args.pipeline)
    if isinstance(sheet, Refusal):
        print(sheet.render(), file=sys.stderr)
        return EXIT_REFUSED

    block = provenance_block(sheet, sources, args.pipeline, args.strandedness, groups)
    if args.out is not None:
        args.out.write_text(sheet.csv_text())
        sys.stdout.write(f"wrote {len(sheet.rows)} row(s) to {args.out}\n")
        sys.stdout.write(block)
    else:
        sys.stdout.write(sheet.csv_text())
        sys.stdout.write("\n")
        sys.stdout.write(block)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

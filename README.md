# bench-to-paper skills

Agent skills for computational biology that stop instead of guessing — a public accession to a pipeline sample sheet, a run manifest to a methods paragraph — and a playbook for using them without letting the agent fill in what it was not told.

## What this is

Two skills and one written discipline, for Claude Code or any tool that reads the Agent Skills format.

- **`accession-to-samplesheet`** — SRR/ERR/DRR accessions in, an nf-core/rnaseq sample sheet out, built only from what ENA records and what you state. Strandedness, grouping, and whether two runs are one sample are yours; the skill stops and names the value when you have not stated it, or when the metadata contradicts you.
- **`methods-write-up`** — a run manifest in, a methods paragraph out, written only from the recorded facts. A sentence with no recorded fact behind it is a visible `[not recorded: …]` marker, never the sentence everybody writes.
- **`PLAYBOOK.md`** — why every skill stops rather than guesses, how provenance runs end to end, what the pack does not do, where a plausible answer is most likely wrong and the one-line check for each, and how to add a skill.

Three more skills (pipeline run, differential expression, figure) are specified in the design and not in this release.

## What this is not

It does not choose your biology. Reference genome, annotation version, experimental design, contrast and threshold stay yours — the pack records them and refuses without them.

It does not check that your choices were right. It checks that a choice was made and written down.

## What each skill does, testably

1. `accession-to-samplesheet` reads ENA's `read_run` record for each accession and writes `sample,fastq_1,fastq_2,strandedness`, then a provenance block naming the field behind every column and the date it was read.
2. It refuses, naming the field, when strandedness is not stated, when a run is in no group, when a run is not RNA-Seq, when ENA lists no FASTQ files, when the read layout and the file count disagree, when runs you joined as one sample have different ENA samples or read layouts, and when one ENA sample is listed as two replicates or placed in two groups.
3. `methods-write-up` writes short atomic sentences, each bound to named manifest fields, with the values verbatim; remove any one field and exactly that sentence becomes a marker naming the field.
4. Both scripts are Python 3.10+ with no packages, and each skill carries its own tests.

## Status

Early. The two skills pass their acceptance checks on saved public ENA records and an example manifest, and nothing else has been tried.

## Install

Python 3.10 or newer, no packages. From an empty project directory:

```
git clone https://github.com/javrodriguez/bench-to-paper-skills
mkdir -p .claude/skills
cp -r bench-to-paper-skills/skills/* .claude/skills/
```

## Smoke

One line, two commands, no network: the methods skill on its example manifest (one field is deliberately absent), then the sample-sheet skill asked for a sheet without a strandedness.

```
python3 .claude/skills/methods-write-up/scripts/methods.py .claude/skills/methods-write-up/examples/manifest.example.json; python3 .claude/skills/accession-to-samplesheet/scripts/samplesheet.py SRR6357070 --group WT=SRR6357070
```

Expected output, verbatim:

```
Reads were processed with nf-core/rnaseq version 3.14.0. The run comprised 6 samples with paired-end reads. Library strandedness was reverse, as declared in the sample sheet. The reference genome was R64-1-1 from Ensembl release 111. Gene annotation was R64-1-1 GTF from Ensembl release 111. Reads were trimmed with Trim Galore version 0.6.10. [not recorded: trimming parameters — needs trimming.parameters] Reads were aligned with STAR version 2.7.10a. Gene-level quantification used Salmon version 1.10.1. The pipeline ran on a single Linux workstation.
REFUSED: strandedness — ENA metadata carries no strandedness field, so it cannot be read; state it with --strandedness {unstranded,forward,reverse,auto} — `auto` means the pipeline measures it
```

The first line is the paragraph with its one marker. The second is the stop: the sheet was not written, and the message names what to state.

## Known limits

See `LIMITS.md` — read it before you use this on anything that goes into a paper.

## Tests

```
pip install pytest
python3 -m pytest -q bench-to-paper-skills/skills
```

## Licence and contributions

MIT — see `LICENSE`.

A new skill needs the same contract as the two here: stated inputs, an explicit refusal clause, and an acceptance check somebody else can run. See `CONTRIBUTING.md`.

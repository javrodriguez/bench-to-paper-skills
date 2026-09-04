# How the expected sheets were made, and what they are

These three sheets are the "known-correct sample sheets" the acceptance check compares
against. **They were written by hand from the saved ENA responses in `../fixtures/`**,
one column at a time — `fastq_1` and `fastq_2` from the `fastq_ftp` field split on `;`
with `ftp://` in front, `strandedness` the value the test supplies, `sample` the group
and replicate position the test supplies — and each value was read back against the
fixture's field by a person. They were not produced by running the script and pasting
its output, and they were not produced by an independent tool.

That makes this a regression oracle plus a human read, not an external ground truth.
It is stated here so nobody mistakes "matches on every column" for "agrees with a
second implementation". The one column that has an external definition, the header,
is quoted from the nf-core/rnaseq usage document in the skill's `SKILL.md`.

| Sheet | Fixture(s) | Read | Case |
|---|---|---|---|
| `paired-single-run.csv` | `SRR6357070.json` | 2026-09-03 (the fixture's `.meta.json` carries the response Date) | one PAIRED run, one replicate, strandedness `auto` |
| `single-end-run.csv` | `DRR170478.json` | 2026-09-03 | one SINGLE run, `fastq_2` empty, strandedness `unstranded` |
| `joined-runs.csv` | `ERR17585769.json`, `ERR17585770.json`, `ERR17585771.json` | 2026-09-03 | three PAIRED runs of one ENA sample (`SAMEA123083811`) joined with `+` into one replicate, so all three rows carry the same `sample` value |

The refusal fixtures, all real ENA records saved the same day: `DRR844501.json` (RNA-Seq,
no FASTQ files listed), `DRR023222.json` (WGS, not RNA-Seq), `SAMN16192427.json` (one
sample with three PAIRED runs and one SINGLE run — the mixed-layout and split-sample stops),
`SRR6357073.json` (a second yeast run for the ungrouped and cross-sample stops).

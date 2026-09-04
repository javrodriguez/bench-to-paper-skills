---
name: accession-to-samplesheet
description: Build an nf-core/rnaseq sample sheet from public sequencing accessions (SRR/ERR/DRR runs, or a sample/experiment/study) using only what ENA records and what the user states. Use when the user wants a samplesheet, a sample sheet, or "the input CSV for the pipeline" from an accession. Stops and names the missing value instead of guessing strandedness, grouping, or which runs are one sample.
---

# accession-to-samplesheet

## The contract (as built)

| | |
|---|---|
| **Purpose** | A public sequencing accession in; a validated pipeline sample sheet out. This release writes the nf-core/rnaseq format: `sample,fastq_1,fastq_2,strandedness`. |
| **Inputs** | One or more accessions; the target pipeline; the strandedness; the experimental grouping — which runs form which replicate of which group, and which runs are one sample sequenced more than once. |
| **Outputs** | The sheet, plus a provenance block naming every run, the ENA field each column came from, the URL and response date it was read at, and which values the user supplied. |
| **Refusal** | If strandedness, read layout, the FASTQ locations, or the group assignment cannot be read from the source metadata or the user's words, the script stops and names the missing field (`REFUSED: <field> for <run> — <why>`, or `REFUSED: <field> — <why>` when the stop is about the whole invocation; exit 2). It never infers a value from the file names or from what is typical, and it stops when the metadata contradicts the grouping (one ENA sample listed as two replicates, or two samples joined as one). |
| **Acceptance check** | Against three public accessions with known-correct sample sheets, the generated sheet matches on every column, and a fourth accession with deliberately incomplete metadata produces a refusal rather than a guess (`tests/test_samplesheet.py`, offline on saved ENA responses). |

## What you do

1. **Collect the four inputs in the user's words.** The accessions; the pipeline (this release: `nf-core/rnaseq`); the strandedness — `unstranded`, `forward`, `reverse`, or `auto` (the pipeline measures it); the grouping. Ask for each one you do not have. Do not propose a strandedness from the library kit, the paper, or habit. Do not assign runs to groups from their titles — you may show the titles the provenance prints so the user can decide.
2. **Run the script:**
   ```
   python3 <this skill's folder>/scripts/samplesheet.py ACC [ACC ...] --pipeline nf-core/rnaseq --strandedness <value> --group NAME=RUN[+RUN...][,RUN...] [--group ...] --out samplesheet.csv
   ```
   A comma separates replicates (`WT_REP1`, `WT_REP2`, …); a `+` joins runs that are one sample sequenced more than once, so they share a `sample` value and the pipeline concatenates them.
3. **On `REFUSED:`, relay the line verbatim and ask for the named value.** Never retry with a guessed value. The common stops: strandedness not stated; a run not named in any group (the message shows its ENA title); two runs listed as separate replicates that ENA records as one sample (join them with `+`, or keep them apart — the user's call); runs joined with `+` that ENA records as different samples or different read layouts; a run that is not RNA-Seq; a run with no FASTQ files in ENA.
4. **Hand over the sheet and the provenance block together.** The provenance is the part that says what was read and what was supplied; do not drop it.

## What you never do

- Choose strandedness, a group, or a merge for the user.
- Edit the sheet after the script writes it.
- Fill a column from a file name or a sample title.

## Reference — the target format, as fetched

From `https://raw.githubusercontent.com/nf-core/rnaseq/master/docs/usage.md`, read 3 September 2026 (response `Date: Thu, 03 Sep 2026 21:18:58 GMT`):

> The pipeline will auto-detect whether a sample is single- or paired-end using the information provided in the samplesheet. The samplesheet can have as many columns as you desire, however, there is a strict requirement for the first 4 columns to match those defined in the table below.

> The `sample` identifiers have to be the same when you have re-sequenced the same sample more than once e.g. to increase sequencing depth. The pipeline will concatenate the raw reads before performing any downstream analysis.

> `strandedness` — Sample strand-specificity. Must be one of `unstranded`, `forward`, `reverse` or `auto`.

Data source: the ENA Portal API, `https://www.ebi.ac.uk/ena/portal/api/filereport?accession=<ACC>&result=read_run&format=json` (public, no key). Strandedness is not among its `read_run` fields, which is why it is always the user's to state.

## Files

- `scripts/samplesheet.py` — the script (Python 3.10+, standard library only); `--from-json` reads a saved response offline, `--save-raw DIR` saves responses verbatim
- `tests/test_samplesheet.py` — the acceptance checks, on saved ENA responses under `tests/fixtures/` with the hand-verified sheets under `tests/expected/`

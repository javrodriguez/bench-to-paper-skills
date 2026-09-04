---
name: methods-write-up
description: Draft the methods paragraph for an RNA-seq analysis from the run manifest and the assumptions note only. Use when the user asks for a methods section, a methods paragraph, or "write up what we ran". Every sentence with no recorded fact behind it becomes a visible [not recorded] marker; the skill never fills one in.
---

# methods-write-up

## The contract (as built)

| | |
|---|---|
| **Purpose** | The methods paragraph, generated only from what the run actually recorded. |
| **Inputs** | A run manifest (JSON, schema in `schema/manifest.schema.md`) and, optionally, an assumptions note from the differential-expression step (JSON). The manifest is written from the run's own records: for an nf-core run, `pipeline_info/software_versions.yml`, the resolved `params.json`, and the sample sheet. |
| **Outputs** | A paragraph of short atomic sentences, plus (`--coverage`) the list of every fact used, every sentence not written and the fields it needed, the `sources` map as declared, and every key ignored. |
| **Refusal** | Any sentence a methods section usually contains that this run cannot support is emitted as `[not recorded: <topic> — needs <fields>]`. The script never writes "reads were trimmed with default parameters" because that is what people usually write. |
| **Acceptance check** | Given a manifest with a field removed, the paragraph loses exactly the corresponding sentence and gains exactly one marker naming that field — run as a sweep over every field (`tests/test_methods.py`). |

_Deviation from the design note this skill was built from (recorded 3 September 2026): the design named "the S2 run manifest and the S3 assumptions note. Nothing else" as inputs. The `pipeline-run` and `differential-expression` skills are not in this release, so the manifest and the note are written by hand from the run's records. The "nothing else" half stands: the script reads no other source._

## What you do

1. **Find the run's own records.** For an nf-core pipeline: `pipeline_info/software_versions.yml` (tool versions), `pipeline_info/params*.json` or the resolved params (reference, executor), the sample sheet (sample count, layout, strandedness as declared). For another pipeline: whatever it wrote. Name each file you open.
2. **Write the manifest** as JSON following `schema/manifest.schema.md`. Every value must be a line you can point at in one of those files, or something the user told you. Fill `sources` with the file (or `user`) per section. **Leave out what you did not find.** A field you are unsure of is a field you leave out; the marker is the honest sentence.
3. **Never fill a field from memory** — not the version "this pipeline usually uses", not "GRCh38" because it is common, not a trimming parameter because it is the tool's default. A blank is a fact you do not have; a plausible value is a fabrication.
4. **Run the script:**
   ```
   python3 <this skill's folder>/scripts/methods.py manifest.json [--assumptions assumptions.json] --coverage
   ```
5. **Hand over the paragraph exactly as printed, markers included.** Then the coverage list, so the user can see what was used and what was not recorded. Do not rewrite a marker into a sentence, do not smooth the prose, do not add a sentence the script did not write. If the user wants a marker gone, the road is a fact in the manifest, then run again.

## What you never do

- Remove or reword a `[not recorded: …]` marker.
- Add a sentence the manifest does not deliver ("Reads were quality-checked with FastQC" when no such field exists in this release — say so instead, and suggest an issue if the field matters).
- Read a value from anywhere but the named files and the user's words.

## Files

- `scripts/methods.py` — the script (Python 3.10+, standard library only)
- `schema/manifest.schema.md` — the fields and the sentence each delivers
- `examples/manifest.example.json`, `examples/assumptions.example.json` — labelled examples, not a real run; the manifest leaves `trimming.parameters` out on purpose so the output shows a marker
- `tests/test_methods.py` — the acceptance check as a sweep

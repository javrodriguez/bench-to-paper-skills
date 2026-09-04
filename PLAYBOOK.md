# Playbook — using these skills without letting the agent invent what it was not told

Two skills and one discipline. The discipline is the product; the skills are where it is
enforced in code.

## 1. The refusal contract — why every skill stops, and how to read a stop

Every skill states the inputs it needs. When one is missing, or when two sources
contradict each other, the skill stops and names the value, instead of choosing a
plausible one and never mentioning it again.

A stop looks like this:

```
REFUSED: strandedness — ENA metadata carries no strandedness field, so it cannot be read; state it with --strandedness {unstranded,forward,reverse,auto} — `auto` means the pipeline measures it
```

Read it as two or three parts: **the value** (`strandedness`), **where** (a run accession,
when the stop is about one run; absent when it is about the whole invocation, as here), **why**. The fix is always the same: supply the value
yourself, or resolve the contradiction yourself, and run again. A stop is not an error
in the tool. A stop that fires when it should not — refusing something the metadata
genuinely records — is a bug, and so is a stop that fails to fire. Both are worth an issue.

The agent's part of the contract: when a script refuses, relay the line verbatim and ask
for the named value. Never retry with a guessed value. Never edit the stop away.

## 2. Provenance end to end — every output names its inputs

`accession-to-samplesheet` writes, after every sheet, a provenance block naming the ENA
field each column came from, the URL it was read from, the response date, and which
values you supplied. `methods-write-up` prints, with `--coverage`, every manifest field it
used and every sentence it could not write. The chain is what lets the methods paragraph
say only what the run recorded: a value that has no source in the chain cannot appear.

Until the `pipeline-run` skill exists (specified, not in this release), the manifest that
feeds `methods-write-up` is written by hand from the run's own records. The `sources` map
in the manifest is where you say which file each section came from. The script echoes it
and does not check it — the honesty of a hand-built manifest is yours.

## 3. What the pack does not do — it does not choose your biology

Reference genome and annotation version, the experimental grouping, whether two runs are
one sample or two, the strandedness, the design, the contrast, the threshold: all yours.
The skills record them and refuse without them. They do not check that the choice was
right. A mismatched reference and annotation produce a valid run and a wrong comparison,
and no skill here can catch that.

## 4. How to check the agent — where a plausible answer is most likely wrong

| Where | The plausible wrong answer | The one-line check |
|---|---|---|
| Strandedness | The agent "knows" the library kit and fills in `reverse` | The sheet's provenance says `supplied by user`; if you did not supply it, it was invented |
| Two runs, one sample | The agent splits them into REP1/REP2, or merges them, without asking | The provenance names every `+` join; ENA's `sample_accession` is printed per run |
| Reference version | "GRCh38" with no release | The manifest's `reference.genome_source` must name the release; else the sentence is a marker |
| Trimming | "with default parameters" | The paragraph never says it; if you see that phrase, the paragraph is not this skill's output |
| A step run outside the pack | The methods paragraph carries the conventional sentence anyway | The step's sentence must be a `[not recorded: …]` marker; if it is prose, someone edited the marker away |

## 5. How to add a skill — the same contract

See `CONTRIBUTING.md`: purpose, inputs (which are the researcher's), outputs with
provenance, a refusal clause, and an acceptance check somebody else can run. The
deterministic part goes in `scripts/`; the refusal lives there, not in the prose.

# Run manifest, schema v1

The manifest is a JSON object. Keys are nested as shown; the script reads them as dotted
names. Every value must be a fact you can point at: a line in a file the run wrote, or
something you stated. **An empty string or null is not a fact** and is treated as absent.

Keys beginning with `_` are comments and are never read. A `sources` object maps each
section to where its values came from (a file path, or `user`); it is echoed in the
coverage output and never checked or invented by the script.

Until the `pipeline-run` skill exists (not in this release), the manifest is written by
hand from the run's own records — for an nf-core run, `pipeline_info/software_versions.yml`,
the resolved `params.json`, and the sample sheet. Write only what those files say.

## Fields and the sentence each one delivers

Each sentence is written only when every field it needs is present. A sentence missing any
field is replaced, in place, by `[not recorded: <topic> — needs <fields>]`.

| Field | Sentence it delivers | Needs also |
|---|---|---|
| `pipeline.name` | Reads were processed with … version …. | `pipeline.version` |
| `pipeline.version` | (same sentence) | `pipeline.name` |
| `samples.count` | The run comprised … samples with … reads. | `samples.layout` |
| `samples.layout` | (same sentence) | `samples.count` |
| `strandedness.value` | Library strandedness was …, …. | `strandedness.how` |
| `strandedness.how` | (same sentence; say how it was determined — declared in the sample sheet, or measured by the pipeline) | `strandedness.value` |
| `reference.genome` | The reference genome was … from …. | `reference.genome_source` |
| `reference.genome_source` | (same sentence) | `reference.genome` |
| `reference.annotation` | Gene annotation was … from …. | `reference.annotation_source` |
| `reference.annotation_source` | (same sentence) | `reference.annotation` |
| `trimming.tool` | Reads were trimmed with … version …. | `trimming.version` |
| `trimming.version` | (same sentence) | `trimming.tool` |
| `trimming.parameters` | Trimming parameters were …. | — |
| `alignment.tool` | Reads were aligned with … version …. | `alignment.version` |
| `alignment.version` | (same sentence) | `alignment.tool` |
| `quantification.tool` | Gene-level quantification used … version …. | `quantification.version` |
| `quantification.version` | (same sentence) | `quantification.tool` |
| `executor.name` | The pipeline ran on …. | — |

## The assumptions note (differential expression), schema v1

A second JSON object, given with `--assumptions`, or a `de` section inside the manifest.
These sentences are written only when an assumptions note is given or a `de` section exists;
otherwise they are not part of the paragraph and the coverage output says so.

| Field | Sentence it delivers | Needs also |
|---|---|---|
| `de.tool` | Differential expression was tested with … version …. | `de.version` |
| `de.version` | (same sentence) | `de.tool` |
| `de.design` | The model design was …. | — |
| `de.contrast` | The contrast tested was …. | — |
| `de.correction` | P-values were adjusted by …. | — |
| `de.threshold` | The significance threshold was …. | — |

## What the paragraph never does

- It never writes a sentence whose facts are absent — no "trimmed with default parameters",
  no "standard pipeline", no adjective standing in for a recorded value.
- It never reads a value from anywhere but the manifest and the assumptions note.
- It never removes a marker. If you remove one by hand, the paragraph is no longer this
  skill's output.

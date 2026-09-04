# Limits

Read this first if the output is going into a paper.

1. **This pack does not validate biology.** It checks that a choice was made and recorded, not that the choice was correct.
2. **Reference genome and annotation versions are yours.** A mismatched pair runs fine and compares wrongly, and nothing here can catch that.
3. **This release has two skills.** `accession-to-samplesheet` and `methods-write-up`. The pipeline-run, differential-expression and figure skills are specified in the design and not built; the methods paragraph is therefore fed by a manifest you write by hand from the run's own records, and its honesty is yours.
4. **The methods paragraph is only as complete as the manifest.** A step done outside what the manifest records leaves no fact for it, so its sentence is missing. It is missing *visibly*, as a `[not recorded: …]` marker — check for those markers before submitting. The paragraph covers one RNA-seq path (trim, align, quantify, one differential-expression contrast); anything else has no sentence and no marker in this release.
5. **The sample sheet reads ENA only, and one format.** Runs not mirrored in ENA with FASTQ files produce a stop, not a sheet. Strandedness is never read from metadata, because ENA does not record it — you state it, or state `auto` and the pipeline measures it. Only the nf-core/rnaseq format is written. The known-correct sheets the acceptance check compares against were verified by hand against the saved ENA records, not produced by an independent tool.
6. **The refusal contract will get in your way sometimes.** It stops when two runs share an ENA sample and you listed them as separate replicates, when runs you joined have different read layouts, when one ENA sample sits in two groups, and when an accession expands to runs of several kinds. Each stop tells you what to state. If you remove the stops, you have a different tool and you own what it says.

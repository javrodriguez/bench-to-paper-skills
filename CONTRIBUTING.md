# Contributing

A new skill is welcome on the same contract as the two here. A skill without a refusal
clause is the thing this pack exists to not be.

## The contract every skill carries

| Part | What it must say |
|---|---|
| **Purpose** | One sentence: what goes in, what comes out. |
| **Inputs** | Every value the skill needs, and which of them are the researcher's to state (never the skill's to choose). |
| **Outputs** | What is written, plus the provenance that names where every value came from. |
| **Refusal** | The conditions under which the skill stops and names the missing or contradictory value. A skill that proceeds on a guess does not belong here. |
| **Acceptance check** | A check somebody other than the author can run, with the data it runs on named. |

## The shape

```
skills/<skill-name>/
  SKILL.md          the contract above, then the procedure the agent follows
  scripts/          the deterministic part — the refusal lives in code, not in prose
  tests/            the acceptance check, runnable with pytest, offline where possible
```

- Python 3.10+, standard library only. No packages.
- A script's refusal prints `REFUSED: <field> for <accession or input> — <why>` and exits 2.
- Fixtures are verbatim saved responses, with the URL and the response date recorded
  beside them. Never a hand-typed record.
- Anything a skill reads from the network is public and needs no key.

## Issues

The second person asking for the same skill is what moves it up. Open an issue with the
workflow you would replace and how you do it today.

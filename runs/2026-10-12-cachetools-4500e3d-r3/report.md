# heal-yield run: cachetools @ 4500e3d

Generated 2026-10-12T07:36:22.945378Z - model `gpt-oss-120b` at temperature 0.0, k = 3.

All definitions are normative in [METRICS.md](../../METRICS.md). Every number here is recomputed by `heal-yield verify` from the artifacts under `raw/`.

## Headline

**Heal yield: 9.5%** (2 of 21 candidates that failed on first pass were rescued)

| Metric | Value | Numerator / denominator |
|---|---|---|
| 1. Generated candidates (N) | 30 | - |
| 2. First-pass build rate | 100.0% | 30 / 30 |
| 3. First-pass green rate | 30.0% | 9 / 30 |
| 4. Post-heal green rate (k=3) | 36.7% | 11 / 30 |
| 5. Heal yield | 9.5% | 2 / 21 |

### Per-round attribution (metric 4)

| Round | Candidates that passed |
|---|---|
| 0 | 9 |
| 2 | 2 |

## 6. Coverage

Line and branch are reported separately; branch coverage does not subsume line coverage in Python. Baseline is measured with the target modules' existing tests removed. **This is not a claim to improve on the maintainers' suites.**

| | Baseline | Final | Delta |
|---|---|---|---|
| Line | 55.2% | 71.5% | 16.3% |
| Branch | 35.1% | 37.8% | 2.7% |
| Line+branch | 52.8% | 67.6% | 14.7% |

Net new covered lines: **91**

## 7. Mutation score

*deferred to increment 2; see METRICS.md metric 7*

## 8. Cost

| | Value |
|---|---|
| Cost basis | **unmetered** - the endpoint reported no price; this is NOT a cost of $0 |
| Total | unmetered |
| Prompt tokens | 58118 |
| Completion tokens | 44205 |
| Per-run ceiling (operator choice) | $1.0000 |
| Ceiling tripped | no |
| $ / surviving test | n/a |
| $ / net-new covered line | n/a |

### Per-repair-round cost attribution

| Round | USD | Prompt tokens | Completion tokens | Calls |
|---|---|---|---|---|
| 0 | unmetered | 6576 | 9389 | 4 |
| 1 | unmetered | 17261 | 11832 | 4 |
| 2 | unmetered | 17620 | 9848 | 4 |
| 3 | unmetered | 16661 | 13136 | 4 |

## 9. Disposition ledger

Every candidate has exactly one terminal disposition.

| Disposition | Count | Meaning |
|---|---|---|
| `passed` | 11 | survived the terminal 5-run gate |
| `collect-error` | 0 | its file failed to collect |
| `build-failure` | 0 | failed the project's collect/build command |
| `still-failing` | 9 | failed after all k repair rounds |
| `still-flaky` | 6 | failed >=1 of 5 in the terminal gate |
| `no-progress-abort` | 0 | identical failure signature across two rounds |
| `no-coverage-increase` | 4 | passed but covered nothing new |
| `timeout` | 0 | exceeded the per-candidate time limit |
| `no-output` | 0 | the model emitted nothing usable |
| `weakened-rejected` | 0 | rejected by the assertion-weakening guard |

**dispositions sum to N = 30 OK**

### Never-healed

The same enum, filtered to candidates that entered at least one repair round and did not survive.

| Disposition | Count |
|---|---|
| `still-failing` | 9 |
| `still-flaky` | 6 |
| `no-progress-abort` | 0 |
| `weakened-rejected` | 0 |
| **total** | **15** |

## 10. Assertion-weakening guard

Rejected repairs: **0** (reported even when zero)

## Provenance

- Modules under test: `cachetools._cachedmethod`, `cachetools._cached`, `cachetools.func`, `cachetools.keys`
- Generator: `/Users/sahil/.venvs/heal-yield-run/bin/python -m heal_yield.generators.anthropic_gen --model gpt-oss-120b --unmetered`
- Per-candidate time limit: 120.0s
- Flake gate: 5 of 5 consecutive executions, applied once to the survivor pool
- Manifest version: 1.0.1
- Headline-eligible: yes

> The per-run USD ceiling and the per-candidate time limit above are **this operator's choices for this run, not heal-yield recommendations**. Both are declared-as-unset in METRICS.md: no measured value exists for either, and the tool has no default for either.

Reproduce the verification with no API key, no Docker and no re-execution:

```
heal-yield verify --run <this directory>
```

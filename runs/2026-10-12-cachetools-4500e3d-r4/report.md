# heal-yield run: cachetools @ 4500e3d

Generated 2026-10-12T08:21:22.511917Z - model `gpt-oss-120b` at temperature 0.0, k = 3.

All definitions are normative in [METRICS.md](../../METRICS.md). Every number here is recomputed by `heal-yield verify` from the artifacts under `raw/`.

## Headline

**Heal yield: 36.8%** (7 of 19 candidates that failed on first pass were rescued)

| Metric | Value | Numerator / denominator |
|---|---|---|
| 1. Generated candidates (N) | 29 | - |
| 2. First-pass build rate | 100.0% | 29 / 29 |
| 3. First-pass green rate | 34.5% | 10 / 29 |
| 4. Post-heal green rate (k=3) | 58.6% | 17 / 29 |
| 5. Heal yield | 36.8% | 7 / 19 |

### Per-round attribution (metric 4)

| Round | Candidates that passed |
|---|---|
| 0 | 10 |
| 1 | 2 |
| 2 | 2 |
| 3 | 3 |

## 6. Coverage

Line and branch are reported separately; branch coverage does not subsume line coverage in Python. Baseline is measured with the target modules' existing tests removed. **This is not a claim to improve on the maintainers' suites.**

| | Baseline | Final | Delta |
|---|---|---|---|
| Line | 55.2% | 74.9% | 19.7% |
| Branch | 35.1% | 63.5% | 28.4% |
| Line+branch | 52.8% | 73.6% | 20.7% |

Net new covered lines: **110**

## 7. Mutation score

*deferred to increment 2; see METRICS.md metric 7*

## 8. Cost

| | Value |
|---|---|
| Cost basis | **unmetered** - the endpoint reported no price; this is NOT a cost of $0 |
| Total | unmetered |
| Prompt tokens | 54477 |
| Completion tokens | 37335 |
| Per-run ceiling (operator choice) | $1.0000 |
| Ceiling tripped | no |
| $ / surviving test | n/a |
| $ / net-new covered line | n/a |

### Per-repair-round cost attribution

| Round | USD | Prompt tokens | Completion tokens | Calls |
|---|---|---|---|---|
| 0 | unmetered | 6577 | 8863 | 4 |
| 1 | unmetered | 17528 | 11722 | 4 |
| 2 | unmetered | 16473 | 8603 | 4 |
| 3 | unmetered | 13899 | 8147 | 4 |

## 9. Disposition ledger

Every candidate has exactly one terminal disposition.

| Disposition | Count | Meaning |
|---|---|---|
| `passed` | 17 | survived the terminal 5-run gate |
| `collect-error` | 0 | its file failed to collect |
| `build-failure` | 0 | failed the project's collect/build command |
| `still-failing` | 3 | failed after all k repair rounds |
| `still-flaky` | 0 | failed >=1 of 5 in the terminal gate |
| `no-progress-abort` | 1 | identical failure signature across two rounds |
| `no-coverage-increase` | 0 | passed but covered nothing new |
| `timeout` | 0 | exceeded the per-candidate time limit |
| `no-output` | 0 | the model emitted nothing usable |
| `weakened-rejected` | 8 | rejected by the assertion-weakening guard |

**dispositions sum to N = 29 OK**

### Never-healed

The same enum, filtered to candidates that entered at least one repair round and did not survive.

| Disposition | Count |
|---|---|
| `still-failing` | 3 |
| `still-flaky` | 0 |
| `no-progress-abort` | 1 |
| `weakened-rejected` | 8 |
| **total** | **12** |

## 10. Assertion-weakening guard

Rejected repairs: **8** (reported even when zero)

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

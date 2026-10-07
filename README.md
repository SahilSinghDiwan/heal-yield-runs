# heal-yield-runs

Append-only run artifacts for [`heal-yield`](https://github.com/SahilSinghDiwan/heal-yield). Layout and rules: `POLICY.md`. One line per run: `INDEX.md`.

## Check a run (no API key, no Docker, no re-execution)

```
pip install git+https://github.com/SahilSinghDiwan/heal-yield@0dec69e
heal-yield verify --run runs/2026-10-07-cachetools-4500e3d-r2
```

## What is here — read this before quoting any number

Two repetitions of one configuration: `cachetools` @ `4500e3d`, manifest v1.0.1, model `gpt-oss-120b` at temperature 0.0, k = 3, run on 2026-10-07.

| Run | N | First-pass green | Post-heal green | Heal yield |
|---|---|---|---|---|
| r1 | 26 | 26.9% | 38.5% | 15.8% (3 of 19) |
| r2 | 25 | 28.0% | 60.0% | 44.4% (8 of 18) |

- **The two repetitions disagree by almost 3x on heal yield.** Same model id, same temperature, same pinned SHA. N differed too (26 vs 25), so the generator did not produce the same candidates. **No headline number is claimed.** The v1 design needs 5 repetitions per repo before a headline is stated; there are 2.
- **The model was reached through a free multi-provider gateway**, not a first-party API. The harness records the model id the gateway reported, `gpt-oss-120b`; it cannot see which backend served each call or whether temperature 0.0 was honoured. A reader cannot reproduce the generation step without an equivalent endpoint. `verify` re-checks the stored artifacts, not the generation.
- **Cost is unmetered.** The endpoint reports no price. r2's report says so. r1's report wrongly prints `$0.0000`; that is a defect in the tool as it was then, fixed afterwards and disclosed here rather than edited, per `POLICY.md`.
- **One target, 4 modules** (`__init__.py` is excluded by the selection rule). This says nothing about other repositories.
- Run artifacts contain absolute paths from the machine that produced them (`/Users/...`). Editing them would break the checksums.

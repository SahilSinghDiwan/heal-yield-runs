# heal-yield-runs

Append-only run artifacts for [`heal-yield`](https://github.com/SahilSinghDiwan/heal-yield). Layout and rules: `POLICY.md`. One line per run: `INDEX.md`.

## Check a run (no API key, no Docker, no re-execution)

```
pip install git+https://github.com/SahilSinghDiwan/heal-yield@5b9edd8
heal-yield verify --run runs/2026-10-07-cachetools-4500e3d-r2
```

## What is here — read this before quoting any number

Six runs of one configuration: `cachetools` @ `4500e3d`, manifest v1.0.1, model `gpt-oss-120b` at temperature 0.0, k = 3, run on 2026-10-07 and 2026-10-12. Five completed; one failed.

| Run | N | First-pass green | Post-heal green | Heal yield |
|---|---|---|---|---|
| r1 | 26 | 26.9% | 38.5% | 15.8% (3 of 19) |
| r2 | 25 | 28.0% | 60.0% | 44.4% (8 of 18) |
| r3 | 30 | 30.0% | 36.7% | 9.5% (2 of 21) |
| r4 | 29 | 34.5% | 58.6% | 36.8% (7 of 19) |
| r5 | — | `generator-failed`, not eligible | | |
| r6 | 27 | 37.0% | 70.4% | 52.9% (9 of 17) |

Across the five complete runs: first-pass green 26.9%–37.0% (median 30.0%); post-heal green 36.7%–70.4% (median 58.6%); **heal yield 9.5%–52.9% (median 36.8%, mean 31.9%)**.

- **The claim this supports is a spread, not a rate.** First-pass green is fairly stable. Heal yield varies by more than 5x between repetitions of the same configuration. A single run's heal yield on this setup should not be read as the tool's heal yield.
- **One run failed and was replaced.** r5 ended `generator-failed` (a gateway 502, after 8 of 16 calls) and cannot be a headline repetition. r6 replaces it. The failure was a gateway fault, not a result, but the choice to replace it is disclosed here. r5 stays in the repository.
- **N differs between runs** (25–30). The generator did not produce the same candidates each time.
- **The model was reached through a free multi-provider gateway.** The harness records the model id the gateway reported. It cannot see which backend served each call or whether temperature 0.0 was honoured. A reader cannot reproduce the generation step without an equivalent endpoint. `verify` re-checks the stored artifacts, not the generation.
- **Cost is unmetered.** The endpoint reports no price. r1's report wrongly prints `$0.0000`; that was a tool defect, fixed afterwards and disclosed here rather than edited, per `POLICY.md`.
- **One target, 4 modules** (`__init__.py` is excluded by the selection rule). This says nothing about other repositories.
- **Run times varied from 3 to about 100 minutes** on the same configuration, which is the gateway's variability and not part of the tool's behaviour.
- Run artifacts contain absolute paths from the machine that produced them (`/Users/...`). Editing them would break the checksums.

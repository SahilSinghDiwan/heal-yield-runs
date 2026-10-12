# Index

One line per run. Rendered from `index.json`.

| Run | N | First-pass green | Post-heal green | Heal yield | Status | Headline-eligible |
|---|---|---|---|---|---|---|
| `2026-10-07-cachetools-4500e3d-r1` | 26 | 26.9% | 38.5% | 15.8% | complete | yes |
| `2026-10-07-cachetools-4500e3d-r2` | 25 | 28.0% | 60.0% | 44.4% | complete | yes |
| `2026-10-12-cachetools-4500e3d-r3` | 30 | 30.0% | 36.7% | 9.5% | complete | yes |
| `2026-10-12-cachetools-4500e3d-r4` | 29 | 34.5% | 58.6% | 36.8% | complete | yes |
| `2026-10-12-cachetools-4500e3d-r5` | 27 | 70.4% | 70.4% | suppressed | generator-failed | no |
| `2026-10-12-cachetools-4500e3d-r6` | 27 | 37.0% | 70.4% | 52.9% | complete | yes |

All rows: `cachetools` @ `4500e3d`, `gpt-oss-120b`, temperature 0.0, k = 3, manifest 1.0.1, cost unmetered.

- **r1:** its `report.md` prints `Total $0.0000`. The cost was *unmetered* (free endpoint), not zero. The tool was fixed afterwards (`heal-yield` `b2b7b3b`); r1 is left as written.
- **r5:** `generator-failed`. The gateway returned a 502 at `cachetools.keys`, round 1, after 8 of 16 calls. Left as written. Its percentages are over the candidates reached and must not be compared.
- **r6:** the replacement for r5. The gateway fault was not a result, so it was replaced rather than counted.

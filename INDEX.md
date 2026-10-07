# Index

One line per run. Rendered from `index.json`.

| Run | Repo @ SHA | Model | N | First-pass green | Post-heal green | Heal yield | Status | Note |
|---|---|---|---|---|---|---|---|---|
| `2026-10-07-cachetools-4500e3d-r1` | cachetools @ 4500e3d | gpt-oss-120b | 26 | 26.9% | 38.5% | 15.8% | complete | cost line misrendered, see below |
| `2026-10-07-cachetools-4500e3d-r2` | cachetools @ 4500e3d | gpt-oss-120b | 25 | 28.0% | 60.0% | 44.4% | complete |  |

**r1 note:** its `report.md` prints `Total $0.0000`. The model was served by a free gateway that reports no price, so cost was *unmetered*, not zero. The tool was fixed afterwards (`heal-yield` `b2b7b3b`); r1 is left exactly as written.

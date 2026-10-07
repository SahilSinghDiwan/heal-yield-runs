# Policy

- A run directory is added in one commit and never modified again. No fixes, no re-renders.
- A run that is wrong is **superseded, not edited**: add the new run and set `superseded_by` on the old entry in `index.json`. The old run's files stay.
- Known defects in a published run are recorded as `notes` in `index.json` and in `INDEX.md`, never by editing the run.
- Truncated and unfavourable runs are committed in full. Publishing the bad ones is the product.
- Repetitions of one configuration are suffixed `-r1`, `-r2`, … in the order they were run.
- `main` disallows force pushes and deletion.
- `manifests/<version>.yaml` is frozen per version; a run keeps pointing at the version it used.

Layout of a run directory is documented in `RUNS-REPO.md` in the `heal-yield` repository.

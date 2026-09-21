# Screenshots

Committed PNGs referenced from the root [README.md](../../README.md). Each is
captured by the `screenshots`-tagged Playwright pass at a 1280×960 viewport,
clipped to the page's main content (the app navbar is not part of the shots).

Regenerate after intentional UI changes:

```bash
./run screenshots
```

The pass self-skips everywhere else (it gates on the `GENERATE_SCREENSHOTS`
env var, which only this command sets) — the regular playwright suite
collects it as skips and never touches these files.

The models-management shots (`models.png`, `model-rows.png`, `row-detail.png`)
need the testapp overlay (plain `main/` has no models to show). Regenerate
them by running the pass in an overlaid scratch copy, then copying the PNGs
back:

```bash
./run createscratch
rsync -a --delete djangoapp/tests/testapp/ourapp/ ../scratch/ourapp/
( cd ../scratch && RUN_PROJECT_TESTS=1 ./run screenshots --noinput )
cp ../scratch/docs/screenshots/models.png \
   ../scratch/docs/screenshots/model-rows.png \
   ../scratch/docs/screenshots/row-detail.png docs/screenshots/
./run cleanscratch
```

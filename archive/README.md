# Archive

Inputs that are not re-creatable from a live source, kept so the frozen analysis can be reproduced exactly.

- `enforcement/dt=2026-10-21/`: the openFDA recall (drug enforcement) pull used by the frozen analysis (cutoff 2026-10-22, see `analysis/results/manifest.json` on main). openFDA keeps changing this feed, so a fresh pull gives slightly different numbers.

To reproduce: copy this folder to `data/raw/enforcement/` on main, use this branch as `data-branch/` at the commit named in the manifest, then run `make analysis`.

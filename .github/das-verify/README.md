# Pre-submission verification for `das-acyclic-bootstrap-874771265`

This directory exists only on the `verify/das-acyclic-bootstrap-874771265` branch.
It is **not** part of the result PR, which changes only
`submissions/das-acyclic-bootstrap-874771265/`.

The workflow `.github/workflows/das-verify.yml` reproduces the upstream PR-admission
worker on GitHub-hosted runners for the exact submission head, using the pinned
upstream verifier, preparation, environment setup and Palomar sandbox unchanged.
The full proof needs about 30 CPU-hours of compilation, more than the hosted
three-hour budget, so the same per-module compilation is spread over several workers:

| Job | Work |
|---|---|
| `env` | Upstream `prepare.mjs` and `setup.py`; ten shared base modules |
| `inputs` | All 6,632 admitted public modules (signed upstream cache where it applies) |
| `shard` ×16 | The 1,168 graph, admission and row certificate modules |
| `final` | The 47 assembly/return/endpoint modules, `Candidate.Main`, the canonical `Solution` wrapper and both exports |
| `kernel` ×3 | Comparator with the Lean kernel, NanoDa, con-ron on the frozen exports, each after the upstream sandbox and positive/mismatch/ill-typed controls |
| `report` | Commits a summary to the `verify-results/das-acyclic-bootstrap-874771265` branch |

`reuse.json` can name an earlier run of this workflow whose environment and module
products (all SHA-256-manifested) are reused; the `final`, `kernel` and `report` jobs then
run again. `run_logged.sh` keeps each step's full output with its report.

`make_driver.py` generates the staged driver from the pinned `verifier/standard/replay.py`
(its SHA-256 is checked) with single-location edits that are listed in its docstring.
No statement, axiom, sandbox, tool or kernel policy is relaxed. Products move between
workers with SHA-256 manifests. The kernels re-check the complete exported proof.

This is a contributor-side reproduction. It is not the maintainers' protected admission
and creates no admission record.

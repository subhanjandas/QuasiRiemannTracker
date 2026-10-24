# Pre-submission evidence for `das-acyclic-bootstrap-874771265`

This branch holds contributor-side evidence only. It is not part of the result PR, and it is
not the maintainers' protected admission. The result PR changes only
`submissions/das-acyclic-bootstrap-874771265/` at commit
`7195a4d8ae01001cb9781c3a706c7bf28cca970a`, on top of upstream `main` `0ce80fdd`.

## Pinned-verifier reproduction on GitHub-hosted workers

Two runs used the workflow on branch `verify/das-acyclic-bootstrap-874771265` (see
`.github/das-verify/README.md` there). That workflow keeps the upstream preparation,
`setup.py`, Palomar sandbox, per-module compiler and canonical Solution wrapper, and spreads
the module compilation over several 4-vCPU / 16 GB workers.

| Stage | Run | Result |
|---|---|---|
| Upstream `prepare.mjs` and `setup.py`, sandbox and comparator controls, 10 shared base modules | [40104400181](https://github.com/subhanjandas/QuasiRiemannTracker/actions/runs/40104400181) | PASS |
| 6,632 admitted public modules (2,923 from the upstream signed cache, 3,707 compiled; 10.4 CPU-h) | 40104400181 | PASS |
| 16 shards: all 1,168 graph, admission and row certificate modules (19.1 CPU-h) | 40104400181 | PASS |
| 47 assembly, supplier, return and endpoint modules, `Candidate.Main` | [40119097039](https://github.com/subhanjandas/QuasiRiemannTracker/actions/runs/40119097039) | PASS |
| Canonical `Solution.lean` (challenge with `174954253 / 200000000`, `exact Candidate.bound χ hs hpole`) compiled and exported | 40119097039 | PASS |
| Comparator with the Lean kernel on the frozen exports | 40119097039 | not finished: 5 h limit reached |
| NanoDa on the frozen export | 40119097039 | not finished: memory ceiling (85% of 16 GB) after 4 h 48 m |
| con-ron on the frozen export | 40119097039 | not finished: 5 h limit reached |

No kernel rejected the proof. Each kernel worker first passed the upstream sandbox controls
and the positive, mismatched-statement and ill-typed comparator controls, so the full-proof
kernel replays need a larger worker. Run 40104400181's own final job stopped on a packaging
bug in this tooling (restored modules repacked by every shard). It was fixed, and run
40119097039 reused the SHA-256-manifested products of run 40104400181.

Results recorded by the compiler in the pinned sandbox (`run-40119097039-1/logs/final/`):

```text
@Candidate.bound : ∀ {q : ℕ} [inst : NeZero q] (χ : DirichletCharacter ℂ q) {s : ℂ},
  174954253 / 200000000 < s.re → ¬(χ = 1 ∧ s = 1) → DirichletCharacter.LFunction χ s ≠ 0
'Candidate.bound' depends on axioms: [propext, Classical.choice, Quot.sound]
```

All 67 printed axiom reports of the final modules list only these three axioms. No module
reported an error.

| Frozen export | Bytes | SHA-256 |
|---|---:|---|
| `Challenge.export` | 350,228,320 | `d2605d6efb424beba1f9730f2d58fbe0054f9a2afd89f18990da9ec1b30664b2` |
| `Solution.export` | 7,109,006,115 | `28ec29ebe31b2107b2f374fd461e049822f4a09822a19317faee2a771afe4989` |

* Library inventory: `4a08c2b88ee650b70d255cb5e67afa1847d7d5cc88d339a0e77d22e19d491bb9`
* Submission trees: own `a9f75bea43507ecb11193ef396309aaa191d3bff`, Lewko
  `0a07c961b4ed9bb9dd2a83bf4d642a2a452a3597`, OpenAI baseline
  `e470d11a2c5b310e5d8fe5a6263acb376aff9cd6`. The last two are the trees verified for PR #70.

The per-module receipts (status, seconds, olean SHA-256) are in `run-*/receipts/`, the
compiler and control logs in `run-*/logs/`, and machine-readable summaries in
`run-*/summary.json`.

## Independent exact re-check of the source graphs

See `independent-graph-check/`. A separate exact-rational implementation of Collet's
`SourceValid` accepts all 82,112 transitions with no broken batch links. It is a cross-check;
the kernels are the authority.

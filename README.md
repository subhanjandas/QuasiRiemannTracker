QRH-Result: das-acyclic-bootstrap-874771265

QRH-Bound: 174954253/200000000

QRH-Decimal: 0.874771265

## Summary

This PR submits a Lean formalization of the Dirichlet boundary

```math
\theta=\frac{174954253}{200000000}=0.874771265.
```

The statement covers every positive modulus, every complex Dirichlet character $`\chi`$, and every complex argument $`s`$ with $`\mathrm{Re}(s)>\theta`$, retaining the principal-character pole exclusion $`(\chi,s)\ne(1,1)`$.

This boundary is $`1.641\times10^{-6}`$ below the verified boundary `0.874772906` of PR #70. It is also below the boundary `0.87477290596` proposed in the open PR #71.

The contribution is an exact parameter refinement of the ordinary-source machinery developed by Hailey Collet (#69) and extended by Mark Lewko (#70). It uses two ordered returns and the original unconditional inverse estimate with price `2`.

**Verification status:**
- **Completed:** contributor-side compilation of the full dependency closure, including `Candidate.Main`. The canonical solution compiled and exported, and the printed axiom audit for `Candidate.bound` reported only `propext`, `Classical.choice` and `Quot.sound`.
- **Not completed:** full Comparator and three-kernel verification, within the tested resource limits.
- **Pending:** protected admission of this PR's exact head.

## Construction

The starting input is Collet's full Hecke-family bound

```math
\beta\le\frac{8747729897}{10000000000},
```

available through the admitted `lewko-acyclic-bootstrap-874772906` dependency. The construction applies the ordinary-source return twice:

| Round | Input family bound | Natural root price $`6(2\theta_{\mathrm{input}}-1)`$ | Output family bound |
|---|---|---|---|
| A | `8747729897/10000000000` | `11243189691/2500000000` | `87477127/100000000` |
| B | `87477127/100000000` | `112431381/25000000` | `174954253/200000000` |

The initial bound supplies Round A, and Round A's conclusion supplies Round B. The proposed final bound is never used as an assumption.

Each round consists of:

- **Natural source.** The existing variable-price natural-source theorem is applied at the root price supplied by the preceding family bound.
- **Acyclic source graph.** 21,527 count transitions and 19,529 physical transitions are checked. Each node uses its immediately preceding source as both LOW and HIGH supplier. Allowance, low fee and high fee are $`10^{-17}`$, $`10^{-12}`$ and $`10^{-10}`$ respectively.
- **Physical return.** The return uses 38 non-old admission windows, each checking all fifteen admissibility guards, and 224 physical row boxes. Each row box carries an exact degree-(2,3) Bernstein identity with a strictly positive rational margin. Dyadic boxes cover $`0\le\delta\le 3/4`$, $`0\le p\le 1/2`$ under one common count envelope. Conductor interpolation supplies the physical schedule. The return reserve is $`10^{-9}`$.

The NF rule keeps its fixed internal reference price `11243277/2500000` throughout. Applying the natural-source theorem at a smaller root price does not replace or strengthen that NF theorem.

Finally, `FamilyTransfer.dirichlet_of_family_beta` transfers the resulting full-family bound to the all-Dirichlet statement.

Round A follows the adaptive-cap construction first proposed as an exact-rational computation, without Lean verification, in [rohanarun/quasi-rh-hillclimb#28](https://github.com/rohanarun/quasi-rh-hillclimb/pull/28). Here the graph is regenerated at the variable root price, and every transition is proved in Lean. The proof submitted here is contained in the Lean source and its declared public dependency. Verification requires no private research archive or numerical search program.

## Proof map

All paths below are relative to `submissions/das-acyclic-bootstrap-874771265/src/Candidate/`.

| File or directory | Role |
|---|---|
| `Main.lean` | Construction overview and the final `Candidate.bound` |
| `TrackerInput.lean`, `InputInterface.lean` | Concrete bindings to the existing family bound, natural-source theorem and NF rule |
| `CoreSource.lean`, `CoreFastSource.lean`, `CoreBridge.lean`, `FastSource.lean` | Computational source predicates and the soundness bridge `CoreBridge.sound` to Collet's `SourceValid` |
| `Graphs/` | 644 batches containing all 82,112 source transitions, each proved by `decide +kernel` |
| `GraphAssembly/` | The four acyclic source-graph inductions |
| `SuppliersA.lean`, `SuppliersB.lean` | Global count and physical suppliers |
| `ReturnA/`, `ReturnB/` | Geometry, admission and row certificates, covers, schedules and return deductions |
| `Endpoint.lean` | The two ordered family-bound deductions |
| `FamilyTransfer.lean` | Transfer from the full-family bound to Dirichlet nonvanishing |

The intermediate `Inputs` structure packages three existing theorems. The final theorem supplies `TrackerInput.admittedInputs` explicitly, and it has no additional arithmetic hypothesis.

All rational witnesses and certificate proofs are included in Lean. The only declared direct dependency is `lewko-acyclic-bootstrap-874772906`; `openai-baseline` is available transitively. 32 files in `ReturnA/` and `ReturnB/` are adapted from Lewko's Apache-2.0 modules and retain his and Collet's notices. Most are renamed copies. `ReturnConstants`, `CountWindows` and `FinalSchedule` carry this submission's constants, windows and schedule.

This PR adds only its submission's `metadata.json` and Lean files. Contributor-side verification tooling and diagnostic evidence are kept outside the result diff.

## Contributor-side verification

**Repository checks.** On this head:

- The repository's `verifier/standard/prepare.mjs` accepts the submission: 7,855 modules, of which 1,223 are new and 6,632 come from the dependency closure. The dependency trees are identical to those verified for PR #70.
- The metadata validator, the `QRH-` declaration parser and the decimal comparison pass, as do `npm test` (316 tests) and `npm run build`.
- The submission is 46.5 MiB in 1,224 files. The dependency closure is 109.3 MiB in 9,545 files.

**Compilation.** Compilation was distributed across GitHub-hosted workers using the upstream preparation, setup, Palomar sandbox and per-module compilation components. The recorded stages cover the full 7,855-module closure, including `Candidate.Main`, using the authenticated baseline cache and validated contributor build products. The generated canonical `Solution.lean` compiled and exported.

The compiler reported:

```text
@Candidate.bound : ∀ {q : ℕ} [inst : NeZero q] (χ : DirichletCharacter ℂ q) {s : ℂ},
  174954253 / 200000000 < s.re → ¬(χ = 1 ∧ s = 1) → DirichletCharacter.LFunction χ s ≠ 0

'Candidate.bound' depends on axioms: [propext, Classical.choice, Quot.sound]
```

**Independent cross-check.** A separate exact-rational implementation rechecked all 82,112 graph transitions against Collet's `SourceValid` conditions. It found no failed transitions or broken batch links. This is a computational cross-check, not a substitute for proof verification.

Evidence:

- [Run 40104400181](https://github.com/subhanjandas/QuasiRiemannTracker/actions/runs/40104400181): environment preparation, admitted inputs and certificate compilation.
- [Run 40119097039](https://github.com/subhanjandas/QuasiRiemannTracker/actions/runs/40119097039): final assembly, `Candidate.Main`, canonical compilation and export, followed by attempted full-proof checker runs.
- [Results and receipts](https://github.com/subhanjandas/QuasiRiemannTracker/tree/verify-results/das-acyclic-bootstrap-874771265): compiler logs, per-module receipts, summaries, full hashes and the independent graph cross-check.
- [Reproduction workflow](https://github.com/subhanjandas/QuasiRiemannTracker/tree/verify/das-acyclic-bootstrap-874771265).

**Both overall workflow runs have a failure conclusion.**
- The first run's final stage hit a packaging error in the contributor tooling.
- The second run reused the first run's manifested build products and completed final compilation and export. Its full-proof checker jobs did not complete within their resource limits.

These runs are not presented as a successful protected admission.

The runs checked commit `7195a4d8ae01001cb9781c3a706c7bf28cca970a`. The proposed result commit, `2a4bdc15726d5724e86381e5d452e615e5b4cf5d`, has the identical Git tree:

```text
5a00ad719cb44c606b8d7fe64ecd9fd48c2b0652
```

Only the commit metadata and signature differ. Protected verification must still check the actual PR head.

## Remaining verification and resources

Measured on 4-vCPU, 16 GB GitHub-hosted workers:

| Item | Recorded value |
|---|---|
| Compilation of the 1,223 new modules | about 19.3 CPU-hours |
| Compilation of the 3,707 dependency modules absent from the signed cache | about 10.4 CPU-hours |
| Canonical `Solution.lean` compilation and export | 849 s |
| Comparator with the Lean kernel | Did not complete within the five-hour budget |
| NanoDa | Terminated at the configured memory ceiling after approximately 4 hours 48 minutes |
| con-ron | Did not complete within the five-hour budget |

The hosted admission worker is therefore expected to exhaust its three-hour budget during compilation, as it did for PR #70. The Comparator, NanoDa and con-ron outcomes above do not establish full-proof acceptance. An extended replay comparable to the one performed for PR #70 would be appreciated. The resources required for completion remain to be established; the kernel phase may need more than the eight-hour judge allowance used there.

The frozen exports are:

| Export | Bytes | SHA-256 |
|---|---:|---|
| `Challenge.export` | 350,228,320 | `d2605d6efb424beba1f9730f2d58fbe0054f9a2afd89f18990da9ec1b30664b2` |
| `Solution.export` | 7,109,006,115 | `28ec29ebe31b2107b2f374fd461e049822f4a09822a19317faee2a771afe4989` |

Admission remains contingent on four things:
- the repository's protected statement, definition and axiom checks;
- acceptance by all three required kernels;
- maintainer review;
- an official verification record generated by the repository's trusted workflow.

## Attribution and AI disclosure

Hailey Collet developed the ordinary-source construction, NF theorem and finite Bernstein return. Mark Lewko supplied the coherent admitted development and the generic transport and schedule interfaces. OpenAI supplied the underlying analytic framework.

Through those developments, this contribution also builds on work by Akash Levy, Zhongpai Gao, timbalud, DaysSky, liqsweep and ArviFoxy. Inherited authorship and license notices are retained. Lean, Mathlib, PrimeNumberTheoremAnd and Rellich–Kondrachov retain their respective authorship and licenses.

New source is MIT-licensed, with the notice in `Main.lean`. Adapted Apache-2.0 source retains its original notices. Publication metadata and public references are in `metadata.json`.

I used OpenAI Codex and Anthropic Claude extensively for research, exact computation, Lean development, audits and the preparation of this write-up.

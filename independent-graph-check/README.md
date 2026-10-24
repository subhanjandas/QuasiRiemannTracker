# Independent exact re-check of the source graphs

`check_graphs.py` re-implements Hailey Collet's `SourceValid` predicate
(`Collet/Record1252270103Finite/SourceFormulas.lean` in the admitted
`lewko-acyclic-bootstrap-874772906` submission) in exact rational arithmetic (gmpy2 `mpq`).
It evaluates it on every `theorem validNNN : SourceValid …` in
`submissions/das-acyclic-bootstrap-874771265/src/Candidate/Graphs/*.lean` at submission head
`7195a4d8ae01001cb9781c3a706c7bf28cca970a`.

The script was written separately from the code that generated the certificates. For each
graph it checks:

* every transition satisfies `SourceValid child low (some high)`, including the gates at both
  width endpoints `[crossing, cap]` and the cubic Bernstein density gates;
* every child uses its immediately preceding node as both LOW and HIGH supplier;
* every node carries allowance `10^-17`, low fee `10^-12` and high fee `10^-10`;
* the first source of each batch equals the last source of the previous batch.

Result (`report.json`): 82,112 transitions (ACount 21,527, APhysical 19,529, BCount 21,527,
BPhysical 19,529), **0 failures**, no broken links. The roots are
`⟨1, 11243189691/2500000000, 11/200, 0, …⟩` for round A and
`⟨1, 112431381/25000000, 11/200, 0, …⟩` for round B. The terminals equal `countCB`, `countCL`,
`physicalB` and `physicalLambda` in `ReturnA/Finite/ReturnConstants.lean` and
`ReturnB/Finite/ReturnConstants.lean`.

Negative controls: perturbing a source's `B` by `10^-9`, its `q` by `-10^-4`, or its `L` by
`10^-3` makes the check fail.

This is a cross-check only. The Lean kernel, NanoDa and con-ron are the authority.

Run: `pip install gmpy2 && python3 -I check_graphs.py <…/src/Candidate> report.json`

# Copyright (c) 2026 Subhanjan Das. MIT. AI-assisted with Anthropic Claude.
"""Generate the staged pre-submission driver from the pinned upstream replay driver.

The upstream protected replay (verifier/standard/replay.py) compiles every module and
runs the kernels in one three-hour job. This candidate needs about 30 CPU-hours of
compilation, so this pre-submission check distributes the same compilation across
several GitHub-hosted workers. The generated driver keeps the upstream code for
everything that matters to soundness and isolation: library and tool authentication,
Palomar sandbox controls, positive/mismatch/ill-typed comparator controls, the trusted
challenge exported before candidate execution, candidate mount controls, the per-module
sandboxed compiler with its 30-minute module limit, and the canonical Solution wrapper.

Changes, each applied to exactly one location of the upstream text:
  * shared deadline: 10800 s -> --budget (each worker stays inside a 6 h job);
  * --mode compile builds only the closure of --targets; --mode final builds the rest
    and stops after exporting Challenge/Solution (kernels run in separate workers);
  * products compiled by earlier workers of the same run are restored (sha256-checked)
    and treated like the upstream authenticated cache;
  * Solution compile/export timeouts 600 s -> 1800 s / 3600 s (actual times recorded).
This is NOT the maintainers' protected admission and issues no admission record.
Usage: python3 make_driver.py <tracker checkout>
"""
from pathlib import Path
import hashlib, sys

def once(text, old, new):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'expected exactly one occurrence, found {count}: {old[:90]!r}')
    return text.replace(old, new)

VERIFY = '''
def _das_post_checks():
    v.verify_tool_snapshot(tools)
    check_libraries()
    assert sha(work/'exports/Challenge.export') == challenge_hash, 'challenge export changed'
    assert inputs == {str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}, 'source changed'
'''

def main():
    root = Path(sys.argv[1]).resolve()
    replay = root / 'verifier/standard/replay.py'
    original = replay.read_text()
    expected = (root / '.github/das-verify/replay.sha256').read_text().split()[0]
    actual = hashlib.sha256(original.encode()).hexdigest()
    if actual != expected:
        raise SystemExit(f'upstream replay.py differs from the pinned revision: {actual}')
    text = original
    text = once(text, 'args = parser.parse_args()', '''parser.add_argument('--mode', choices=['compile', 'final'], required=True)
parser.add_argument('--targets', type=Path, required=True)
parser.add_argument('--prebuilt', type=Path, action='append', default=[])
parser.add_argument('--products-out', type=Path, required=True)
parser.add_argument('--budget', type=int, required=True)
args = parser.parse_args()''')
    text = once(text, 'v.install_execution_deadline(budget_seconds=10800)',
                'v.install_execution_deadline(budget_seconds=args.budget)')
    text = once(text, "stage('compile standard candidate')\n", '''import das_stage
cached_modules |= das_stage.restore_prebuilt(args.prebuilt, work/'candidate-lib')
print(f'{len(cached_modules)} modules available from this run or the signed cache', flush=True)
''' + VERIFY + '''stage('compile standard candidate')
''')
    text = once(text, '''order = contract['build_order']
dependencies = contract.get('module_dependencies', {name:order[max(0, i-1):i] for i, name in enumerate(order)})
compile_modules(order, dependencies, compile_one, jobs=jobs,
    is_memory_error=lambda error: isinstance(error, v.ResourceExhausted) and 'result oom-kill)' in str(error))
''', '''order, dependencies, required = das_stage.select(contract, args.targets, cached_modules, args.mode)
_completed, _failure, _seconds = das_stage.run_compile(order, dependencies, compile_one, jobs,
    lambda error: isinstance(error, v.ResourceExhausted) and 'result oom-kill)' in str(error))
das_stage.finish_compile(args, work, contract, order, required, cached_modules,
    _completed, _failure, _seconds, _das_post_checks)
''')
    text = once(text, "tools=tools,timeout=600))\nlog('solution-export'", "tools=tools,timeout=1800))\nlog('solution-export'")
    text = once(text, "executable_paths=[old,exporter,Path('/usr')],tools=tools,timeout=600))\nv.verify_export(work/'exports/Solution.export')",
                "executable_paths=[old,exporter,Path('/usr')],tools=tools,timeout=3600))\nv.verify_export(work/'exports/Solution.export')")
    text = once(text, "stage('compile and export standard solution wrapper')\n",
                "stage('compile and export standard solution wrapper')\n_solution_started = time.monotonic()\n")
    # Stop before the judge: the three kernels run in separate full-size workers.
    head, sep, _tail = text.partition("stage('Comparator and Lean, NanoDa, con-ron')\n")
    if not sep:
        raise SystemExit('judge stage marker missing')
    text = head + '''das_stage.finish_final(args, work, contract, config, challenge_hash,
    time.monotonic() - _solution_started, _das_post_checks)
'''
    out = root / 'verifier/standard/das-driver.py'
    compile(text, str(out), 'exec')
    out.write_text(text)
    (root / 'verifier/standard/das_stage.py').write_text((root / '.github/das-verify/das_stage.py').read_text())
    print(f'generated {out} sha256={hashlib.sha256(text.encode()).hexdigest()} from replay.py sha256={actual}')

if __name__ == '__main__':
    main()

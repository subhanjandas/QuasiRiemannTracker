# Copyright (c) 2026 Subhanjan Das. MIT. AI-assisted with Anthropic Claude.
"""Run one of the three required checks on the frozen Challenge/Solution exports.

This reproduces the per-kernel decomposition of the pinned upstream
verifier/standard/judge.py (used upstream when several kernel jobs fit in memory),
with each check on its own full-size worker:
  * "Lean default": Comparator compares the canonical statement, transitive
    definitions and permitted axioms, and replays the proof with the Lean kernel;
  * "nanoda" and "con-ron": the protected external kernels on the identical export.
Before the check, the worker repeats the upstream Palomar sandbox controls and the
positive / mismatched-statement / ill-typed comparator controls with all kernels.
Only propext, Classical.choice and Quot.sound are permitted.
Usage: python3 das_kernel.py --kernel NAME --exports DIR --final-report FILE --out DIR
"""
from pathlib import Path
import argparse, datetime, hashlib, json, os, subprocess, sys, time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'verifier'))
from worker_resources import worker_capacity

sha = lambda p: hashlib.file_digest(open(p, 'rb'), 'sha256').hexdigest()
parser = argparse.ArgumentParser()
parser.add_argument('--kernel', choices=['Lean default', 'nanoda', 'con-ron'], required=True)
parser.add_argument('--exports', type=Path, required=True)
parser.add_argument('--final-report', type=Path, required=True)
parser.add_argument('--timeout', type=int, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
if sys.flags.optimize or os.getuid() == 0:
    raise SystemExit('Use unoptimized Python as an unprivileged worker user')
OUT = ROOT / 'verification'
profile = json.loads((OUT / 'profile.json').read_text())
ref = Path(profile['palomar']).resolve()
sys.path.insert(0, str(ref))
from scripts import verify_submission as v
assert sha(ref / 'scripts/verify_submission.py') == 'c575759d82c506f181b3736a110950fd32931c08a1be454262027d6205f178a2'
work = args.out.resolve()
work.mkdir(parents=True, exist_ok=True)
for name in ['logs', 'home', 'tmp', 'control', 'preflight']:
    (work / name).mkdir(exist_ok=True)
judge = Path(profile['judge_toolchain']).resolve()
v._BWRAP = Path(profile.get('bwrap', '/usr/bin/bwrap'))
v.VERIFICATION_LIMITS = {**v.VERIFICATION_LIMITS, 'memory_high_percent': 75, 'memory_max_percent': 85, 'tasks_max': 256}
v.install_execution_deadline(budget_seconds=args.timeout + 1800)
bundled = {name: judge / 'bin' / name for name in v.TOOLCHAIN_TOOLS}
approved = json.loads((OUT / 'tool-pins.json').read_text())
assert {('judge_' + n): sha(p) for n, p in bundled.items()} == {k: d for k, d in approved.items() if k.startswith('judge_')}, 'Checker tool pins differ'
pinned = json.loads((ROOT / 'verifier/standard/tool-pins.json').read_text())
assert all(approved[k] == d for k, d in pinned.items() if k != 'exporter'), 'Checker tools differ from protected pins'
python, touch = Path('/usr/bin/python3').resolve(), Path('/usr/bin/touch')
tools = v.tool_snapshot([*bundled.values(), v._BWRAP, python, touch])
capacity = worker_capacity()
threads = capacity['threads']
env = {'PATH': str(judge / 'bin') + ':/usr/bin:/bin', 'HOME': str(work / 'home'), 'TMPDIR': str(work / 'tmp'),
       'LANG': 'C.UTF-8', 'LEAN_ABORT_ON_PANIC': '1'}
system = v.system_readable_paths()
phases = []


def stage(name):
    phases.append({'phase': name, 'at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    (work / 'phases.json').write_text(json.dumps(phases, indent=2) + '\n')
    print(name, flush=True)


stage('sandbox controls')
probe = work / 'control/read.txt'
probe.write_text('positive read control\n')
v.verify_sandbox_confinement(work / 'control/denied-write', work / 'denied-read', positive_read=probe, python=python, touch=touch,
    cwd=work / 'control', environment=env, writable_directories=[work / 'home', work / 'tmp'],
    protected_write_directories=[work / 'control'], readable_paths=[work / 'control', *system],
    executable_paths=[judge, Path('/usr')], tools=tools)
stage('positive, mismatched statement and ill-typed proof controls')
v.comparator_preflight(work / 'preflight', lean=bundled['lean'], leanexport=bundled['leanexport'], lake=bundled['lake'],
    lean_prefix=judge, bwrap=v._BWRAP, kernels=v.protected_kernels(bundled), primitives=v.primitive_targets(judge),
    environment=env, executable_paths=[judge, v._BWRAP, Path('/usr')], tools=tools, timeout=300)
control_root = work / 'preflight/comparator-preflight'
controls = []
for module, expected in [('PalomarPreflightSolution', 'accepted'), ('PalomarPreflightWrong', 'statement-mismatch'),
                         ('PalomarPreflightIllTyped', 'ill-typed-proof')]:
    control = v.judge_exports(lake=bundled['lake'], config=control_root / 'comparator.json',
        challenge_export=control_root / 'exports/PalomarPreflightChallenge.export',
        solution_export=control_root / 'exports' / (module + '.export'), scratch=work / ('control-' + module),
        bwrap=v._BWRAP, lean_prefix=judge, environment=env, tools=tools, timeout=300)
    transcript = control.stdout + '\n' + control.stderr
    (work / 'logs' / ('control-' + module + '.log')).write_text(transcript)
    if expected == 'accepted':
        assert control.returncode == 0 and 'Your solution is okay!' in transcript
        assert all(k + ' kernel accepts the solution' in transcript for k in ['Lean default', 'nanoda', 'con-ron'])
    elif expected == 'statement-mismatch':
        assert control.returncode != 0 and 'Challenge and solution theorem statement do not match' in transcript
    else:
        assert control.returncode != 0 and 'Lean default kernel rejected the solution' in transcript
    controls.append({'expected': expected, 'exit_code': control.returncode})
(work / 'controls.json').write_text(json.dumps(controls, indent=2) + '\n')

stage('authenticate frozen exports')
final = json.loads(args.final_report.read_text())
exports = {}
for name in ['Challenge.export', 'Solution.export']:
    packed = args.exports / (name + '.zst')
    target = work / name
    subprocess.run(['zstd', '-d', '-q', '-f', str(packed), '-o', str(target)], check=True)
    assert sha(target) == final['exports'][name]['sha256'], f'{name} differs from the final worker'
    target.chmod(0o444)
    exports[name] = target
v.verify_export(exports['Challenge.export'])
v.verify_export(exports['Solution.export'])
config = {'challenge_module': 'Challenge', 'solution_module': 'Solution', 'theorem_names': ['QRH.canonical_bound'],
          'definition_names': [], 'permitted_axioms': sorted(v.STANDARD_AXIOMS), 'external_kernels': v.protected_kernels(bundled)}
assert config == final['comparator_config'], 'comparator configuration differs from the final worker'

stage(args.kernel + ' check')
started = time.monotonic()
scratch = work / 'judge'
scratch.mkdir()
if args.kernel == 'Lean default':
    lean_config = scratch / 'comparator-lean.json'
    lean_config.write_text(json.dumps({**config, 'external_kernels': {}}))
    result = v.judge_exports(lake=bundled['lake'], config=lean_config, challenge_export=exports['Challenge.export'],
        solution_export=exports['Solution.export'], scratch=scratch / 'lean', bwrap=v._BWRAP, lean_prefix=judge,
        environment=env, tools=tools, timeout=args.timeout)
    transcript = result.stdout + '\n' + result.stderr
    accepted = (result.returncode == 0 and 'Your solution is okay!' in transcript
                and 'Lean default kernel accepts the solution' in transcript)
else:
    command = v.protected_kernels(bundled)[args.kernel]
    if args.kernel == 'con-ron':
        command = [command[0], f"--jobs={max(1, min(2, threads))}"]
    directory = scratch / args.kernel
    directory.mkdir()
    config_path = directory / 'kernel.json'
    config_path.write_text(json.dumps({
        'use_stdin': False, 'export_file_path': str(exports['Solution.export']),
        'permitted_axioms': config['permitted_axioms'], 'unpermitted_axiom_hard_error': False,
        'num_threads': max(1, min(4, threads)), 'nat_extension': True, 'string_extension': True}))
    kernel_args = [*command, str(config_path if args.kernel == 'nanoda' else exports['Solution.export'])]
    result = v.sandboxed_run(kernel_args, cwd=directory,
        environment={'PATH': str(judge / 'bin') + ':/usr/bin:/bin', 'HOME': str(directory), 'TMPDIR': str(directory),
                     'LANG': 'C.UTF-8', 'LEAN_ABORT_ON_PANIC': '1'},
        writable_directories=[directory], readable_paths=[config_path, exports['Solution.export'], *system],
        executable_paths=[judge, Path('/usr')], tools=tools, timeout=args.timeout, check=False)
    message = f'{args.kernel} kernel accepts the solution' if result.returncode == 0 else f'{args.kernel} kernel rejected the solution'
    transcript = result.stdout + '\n' + result.stderr + '\n' + message
    accepted = result.returncode == 0
seconds = time.monotonic() - started
(work / 'logs' / 'judge.log').write_text(transcript)
v.verify_tool_snapshot(tools)
for name, path in exports.items():
    assert sha(path) == final['exports'][name]['sha256']
stage('accepted' if accepted else 'rejected')
report = {'kernel': args.kernel, 'accepted': accepted, 'exit_code': result.returncode, 'seconds': round(seconds, 1),
          'head_sha': final['head_sha'], 'exports': final['exports'], 'permitted_axioms': config['permitted_axioms'],
          'controls': controls, 'sandbox_controls': 'PASS', 'threads': threads,
          'memory_bytes': capacity['memory_bytes'], 'tool_pins': approved,
          'palomar_sha256': sha(ref / 'scripts/verify_submission.py'), 'driver_sha256': sha(Path(__file__)),
          'transcript_tail': transcript[-6000:]}
(work / 'kernel-report.json').write_text(json.dumps(report, indent=1) + '\n')
for path in exports.values():
    path.unlink()
print(json.dumps({key: value for key, value in report.items() if key not in ('transcript_tail', 'tool_pins')}, indent=1), flush=True)
print(transcript[-3000:], flush=True)
if not accepted:
    sys.exit(1)

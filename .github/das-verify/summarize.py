# Copyright (c) 2026 Subhanjan Das. MIT. AI-assisted with Anthropic Claude.
"""Collect the per-worker reports of one pre-submission run into a small results tree.
Usage: python3 summarize.py <downloaded reports dir> <output dir>
"""
from pathlib import Path
import json, os, re, shutil, sys

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
run = {'run_id': os.environ.get('GITHUB_RUN_ID'), 'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
       'workflow_sha': os.environ.get('GITHUB_SHA'), 'repository': os.environ.get('GITHUB_REPOSITORY'),
       'run_url': f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}",
       'submission_head': os.environ.get('QRH_HEAD'),
       'products_from_run': os.environ.get('QRH_REUSE_RUN') or os.environ.get('GITHUB_RUN_ID')}
stages, axiom_lines, bad_axioms, errors = {}, {}, [], {}
AX = re.compile(r"^'([^']+)' depends on axioms: \[(.*)\]\s*$")
NOAX = re.compile(r"^'([^']+)' does not depend on any axioms\s*$")
for directory in sorted(p for p in src.iterdir() if p.is_dir()):
    name = directory.name.removeprefix('reports-')
    entry = {}
    for report in ['compile-report.json', 'final-report.json', 'kernel-report.json']:
        path = directory / report
        if path.is_file():
            value = json.loads(path.read_text())
            receipts = value.pop('receipts', None)
            if receipts is not None:
                (out / 'receipts').mkdir(exist_ok=True)
                (out / 'receipts' / f'{name}.json').write_text(json.dumps(receipts, indent=0, sort_keys=True) + '\n')
            entry[report] = value
    logs = directory / 'logs'
    if logs.is_dir():
        target = out / 'logs' / name
        target.mkdir(parents=True, exist_ok=True)
        for log in sorted(logs.glob('*.log')):
            shutil.copyfile(log, target / log.name)
            text = log.read_text(errors='replace')
            for line in text.splitlines():
                m = AX.match(line.strip())
                if m:
                    axioms = sorted(a.strip() for a in m.group(2).split(',') if a.strip())
                    axiom_lines[m.group(1)] = axioms
                    if not set(axioms) <= {'propext', 'Classical.choice', 'Quot.sound'}:
                        bad_axioms.append((m.group(1), axioms))
                m = NOAX.match(line.strip())
                if m:
                    axiom_lines[m.group(1)] = []
            if re.search(r'(^|\n)\S*:\d+:\d+: error', text):
                errors[f'{name}/{log.name}'] = [l for l in text.splitlines() if ': error' in l][:20]
    for extra in ['controls.json', 'phases.json']:
        if (directory / extra).is_file():
            (out / 'logs' / name).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(directory / extra, out / 'logs' / name / extra)
    stages[name] = entry


def status(name):
    entry = stages.get(name, {})
    if 'kernel-report.json' in entry:
        return 'ACCEPTED' if entry['kernel-report.json'].get('accepted') else 'REJECTED'
    if 'final-report.json' in entry:
        return 'EXPORTED'
    report = entry.get('compile-report.json')
    if report is None:
        return 'NO REPORT'
    return 'PASS' if report.get('failure') is None and report.get('post_checks_tools_libraries_source_challenge') is True else 'FAIL'


summary = {'run': run, 'stages': {n: status(n) for n in stages}, 'axioms_printed': axiom_lines,
           'non_standard_axioms': bad_axioms, 'compile_errors': errors,
           'stage_details': {n: {k: {kk: vv for kk, vv in v.items() if kk not in ('slowest',)} for k, v in e.items()} for n, e in stages.items()}}
kernels = {n: s for n, s in summary['stages'].items() if n.startswith('kernel-')}
summary['all_three_kernels_accept'] = len(kernels) == 3 and all(s == 'ACCEPTED' for s in kernels.values())
summary['candidate_bound_axioms'] = axiom_lines.get('Candidate.bound')
(out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
lines = ['# Pre-submission verification run', '',
         'This run is a contributor-side reproduction on GitHub-hosted workers. It is not the',
         "maintainers' protected admission and does not create an admission record.", '',
         f"* Run: {run['run_url']}", f"* Submission head: `{run['submission_head']}`",
         f"* Workflow commit: `{run['workflow_sha']}`",
         f"* Environment and module products from run: {run['products_from_run']}"
         + ('' if run['products_from_run'] == run['run_id'] else ' (stages not listed below are in that run\'s results directory)'), '',
         '| Stage | Status |', '|---|---|']
lines += [f'| {n} | {s} |' for n, s in summary['stages'].items()]
lines += ['', f"* `Candidate.bound` axioms: {summary['candidate_bound_axioms']}",
          f"* Declarations with non-standard axioms: {len(bad_axioms)}",
          f"* Modules with compile errors: {len(errors)}",
          f"* Comparator + Lean, NanoDa and con-ron all accept: {summary['all_three_kernels_accept']}"]
(out / 'SUMMARY.md').write_text('\n'.join(lines) + '\n')
print('\n'.join(lines))

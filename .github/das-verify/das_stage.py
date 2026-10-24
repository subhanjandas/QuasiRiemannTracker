# Copyright (c) 2026 Subhanjan Das. MIT. AI-assisted with Anthropic Claude.
"""Helpers imported by the generated staged driver (see make_driver.py).

Products move between workers of one workflow run as zstd-compressed tar archives
with a sha256 manifest. Restored products are authenticated file by file and are
used exactly like the upstream authenticated build cache: their modules are skipped
by the compiler. The final kernels re-check the complete exported proof regardless.
"""
from pathlib import Path
import hashlib, json, os, shutil, subprocess, sys, tarfile, threading, time

SUFFIXES = ['.olean', '.olean.private', '.olean.server']


def sha(path):
    with open(path, 'rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def module_files(lib, module):
    rel = module.replace('.', '/')
    return [Path(str(lib / rel) + suffix) for suffix in SUFFIXES]


def restore_prebuilt(archives, lib):
    """Extract authenticated product archives into the read-only candidate library."""
    restored = set()
    for archive in archives:
        archive = Path(archive)
        manifest = json.loads((archive.parent / (archive.name + '.manifest.json')).read_text())
        tar_path = archive.with_suffix('')
        subprocess.run(['zstd', '-d', '-q', '-f', str(archive), '-o', str(tar_path)], check=True)
        with tarfile.open(tar_path) as tar:
            members = tar.getmembers()
            for member in members:
                if not member.isfile() or member.name.startswith('/') or '..' in Path(member.name).parts:
                    raise ValueError(f'unsafe product member {member.name}')
            digests = {rel: d for files in manifest['modules'].values() for rel, d in files.items()}
            if {m.name for m in members} != set(digests):
                raise ValueError(f'{archive.name}: archive members differ from manifest')
            for member in members:
                target = lib / member.name
                if target.exists():
                    # A product restored from an earlier archive may be repeated
                    # byte for byte; any differing duplicate is rejected.
                    if sha(target) != digests[member.name]:
                        raise ValueError(f'conflicting duplicate product {member.name}')
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, open(target, 'xb') as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o444)
        tar_path.unlink()
        archive.unlink()  # free disk; the manifest stays for reporting
        for module, files in manifest['modules'].items():
            for rel, digest in files.items():
                if sha(lib / rel) != digest:
                    raise ValueError(f'product hash mismatch: {rel}')
            if not (lib / (module.replace('.', '/') + '.olean')).is_file():
                raise ValueError(f'missing olean for {module}')
            restored.add(module)
        print(f'Restored {len(manifest["modules"])} authenticated modules from {archive.name}', flush=True)
    return restored


def closure(contract, roots):
    deps = contract['module_dependencies']
    seen, stack = set(), list(roots)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        if name not in deps:
            raise ValueError(f'unknown module {name}')
        seen.add(name)
        stack.extend(deps[name])
    return seen


def select(contract, targets_path, cached, mode):
    targets = json.loads(Path(targets_path).read_text())
    if not isinstance(targets, list) or not targets:
        raise ValueError('targets must be a nonempty JSON list')
    needed = closure(contract, targets)
    order = [name for name in contract['build_order'] if name in needed]
    dependencies = {name: contract['module_dependencies'][name] for name in order}
    required = [name for name in order if name not in cached]
    if mode == 'final' and set(targets) != {'Candidate.Main'}:
        raise ValueError('final mode builds the complete Candidate.Main closure')
    print(f'Selected {len(order)} modules; {len(required)} to compile; {len(order) - len(required)} restored', flush=True)
    return order, dependencies, required


def run_compile(order, dependencies, compile_one, jobs, is_memory_error):
    from standard.compile import compile_modules
    completed, seconds, lock = set(), {}, threading.Lock()

    def tracked(name, threads):
        started = time.monotonic()
        compile_one(name, threads)
        with lock:
            completed.add(name)
            seconds[name] = round(time.monotonic() - started, 1)
    failure = None
    try:
        compile_modules(order, dependencies, tracked, jobs=jobs, is_memory_error=is_memory_error)
    except Exception as error:  # keep successfully returned modules; report the failure
        failure = error
    return completed, failure, seconds


def copy_logs(work, out):
    logs = out / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    for path in sorted((work / 'logs').glob('*.log')):
        name = path.name
        if (name.startswith(('compile-Candidate.', 'resource-', 'challenge-', 'solution-', 'control-'))
                or name in {'judge.log'}):
            shutil.copyfile(path, logs / name)
    # All other compiler logs (public dependencies) in one archive.
    with tarfile.open(out / 'all-logs.tar.gz', 'w:gz') as tar:
        for path in sorted((work / 'logs').glob('*.log')):
            tar.add(path, arcname=path.name)
    for name in ['controls.json', 'phases.json', 'tools.json', 'comparator.json']:
        if (work / name).is_file():
            shutil.copyfile(work / name, out / name)


def pack(lib, modules, archive):
    manifest = {'modules': {}}
    tar_path = archive.with_suffix('')
    with tarfile.open(tar_path, 'w') as tar:
        for module in modules:
            files = {}
            for path in module_files(lib, module):
                if path.exists():
                    if path.is_symlink() or not path.is_file():
                        raise ValueError(f'irregular product {path}')
                    rel = str(path.relative_to(lib))
                    files[rel] = sha(path)
                    tar.add(path, arcname=rel)
            if not any(rel.endswith('.olean') for rel in files):
                raise ValueError(f'no olean for {module}')
            manifest['modules'][module] = files
    subprocess.run(['zstd', '-T0', '-3', '-q', '-f', '--rm', str(tar_path), '-o', str(archive)], check=True)
    (archive.parent / (archive.name + '.manifest.json')).write_text(json.dumps(manifest, sort_keys=True) + '\n')
    return manifest


def finish_compile(args, work, contract, order, required, cached, completed, failure, seconds, verify):
    out = args.products_out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lib = work / 'candidate-lib'
    # Pack everything this worker produced or restored from the signed cache, but
    # not products restored from earlier workers (they already have archives).
    prebuilt = set()
    for archive in args.prebuilt:
        prebuilt |= set(json.loads((Path(archive).parent / (Path(archive).name + '.manifest.json')).read_text())['modules'])
    # compile_one returns immediately for restored modules; count only real compilations.
    compiled = {name for name in completed if name not in cached}
    seconds = {name: s for name, s in seconds.items() if name in compiled}
    new = [name for name in order if name not in prebuilt and (name in compiled or name in cached)]
    receipts = {}
    for name in order:
        if name in compiled:
            receipts[name] = {'status': 'compiled', 'seconds': seconds.get(name),
                              'olean_sha256': sha(lib / (name.replace('.', '/') + '.olean'))}
        elif name in cached:
            receipts[name] = {'status': 'restored-prebuilt' if name in prebuilt else 'restored-signed-cache'}
        else:
            receipts[name] = {'status': 'not-built'}
    copy_logs(work, out)
    if new:
        pack(lib, new, out / 'products.tar.zst')
    verified = None
    try:
        verify()
        verified = True
    except Exception as error:
        verified = f'FAILED: {error}'
    report = {
        'mode': args.mode, 'head_sha': contract['head_sha'], 'repository': contract['repository'],
        'targets_file': str(args.targets), 'selected': len(order), 'required': len(required),
        'compiled': len(compiled), 'restored': len([n for n in order if n in cached]),
        'packed': len(new), 'failure': None if failure is None else f'{type(failure).__name__}: {failure}'[-4000:],
        'post_checks_tools_libraries_source_challenge': verified,
        'compile_cpu_seconds': round(sum(s for s in seconds.values() if s), 1),
        'slowest': sorted(((s, n) for n, s in seconds.items()), reverse=True)[:15],
        'receipts': receipts,
    }
    (out / 'compile-report.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'receipts'}, indent=1), flush=True)
    if failure is not None:
        raise failure
    if verified is not True:
        raise AssertionError(verified)
    missing = [name for name in required if name not in completed]
    if missing:
        raise AssertionError(f'{len(missing)} modules were not compiled')
    if args.mode == 'compile':
        print('Compile stage complete', flush=True)
        sys.exit(0)


def finish_final(args, work, contract, config, challenge_hash, solution_seconds, verify):
    out = args.products_out.resolve()
    exports = out / 'exports'
    exports.mkdir(parents=True, exist_ok=True)
    verify()
    info = {}
    for name in ['Challenge.export', 'Solution.export']:
        path = work / 'exports' / name
        info[name] = {'sha256': sha(path), 'bytes': path.stat().st_size}
        subprocess.run(['zstd', '-T0', '-3', '-q', '-f', str(path), '-o', str(exports / (name + '.zst'))], check=True)
    if info['Challenge.export']['sha256'] != challenge_hash:
        raise AssertionError('challenge export changed')
    copy_logs(work, out)
    report = {
        'stage': 'Solution wrapper compiled and exported; kernels pending in separate workers',
        'head_sha': contract['head_sha'], 'source_commit': contract['source_commit'],
        'repository': contract['repository'], 'result_id': contract['manifest']['id'],
        'theta': contract['manifest']['theta'], 'exports': info,
        'solution_compile_and_export_seconds': round(solution_seconds, 1),
        'comparator_config': config, 'library_inventory_sha256': contract['library_inventory_sha256'],
        'submission_trees': contract['submission_trees'],
    }
    (out / 'final-report.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(report, indent=1), flush=True)

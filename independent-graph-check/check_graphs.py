"""Independent exact re-check of every source-graph transition in the submission.

This re-implements Hailey Collet's `SourceValid` predicate (Collet/Record1252270103Finite/
SourceFormulas.lean in the admitted Lewko submission) with exact rationals and evaluates
it on every `theorem validNNN : SourceValid sourceNNN sourceMMM (some sourceKKK)` in
src/Candidate/Graphs/*.lean.  It also checks that consecutive batches link (the first
source of a batch equals the last source of the previous batch), that every node carries
the fixed allowance/fees, and reports the root and terminal source of each family.

It is a cross-check only; the Lean kernel (and NanoDa / con-ron) remain the authority.
Usage: python3 -I check_graphs.py <submission src/Candidate dir> <out.json>
"""
import json, re, sys, os, time
from multiprocessing import Pool
from gmpy2 import mpq

Q = mpq
num = r'(?:\d+(?:/\d+(?:\^\d+)?)?)'
field = re.compile(r'^\(?\s*(\d+)\s*(?:/\s*(\d+)\s*(?:\^\s*(\d+))?)?\s*\)?$')


def rat(text):
    m = field.match(text.strip())
    if not m:
        raise ValueError('unparsed rational: ' + text)
    a = int(m.group(1))
    if m.group(2) is None:
        return Q(a)
    d = int(m.group(2))
    if m.group(3) is not None:
        d = d ** int(m.group(3))
    return Q(a, d)


SRC = re.compile(r'^def (source\d+) : Source := ⟨(.*)⟩\s*$')
VALID = re.compile(r'^theorem (valid\d+) : SourceValid (source\d+) (source\d+) \((some (source\d+)|none)\) := by')


class S:
    __slots__ = ('B', 'L', 'cap', 'q', 'allowance', 'lowFee', 'highFee')

    def __init__(self, vals):
        (self.B, self.L, self.cap, self.q, self.allowance, self.lowFee, self.highFee) = vals

    def tup(self):
        return tuple(str(x) for x in (self.B, self.L, self.cap, self.q, self.allowance, self.lowFee, self.highFee))


KREF = Q(11243277, 2500000)


def crossing(n, low):
    return (low.B - n.B) / (low.L - n.L)


def sourceDen(n, low):
    return 1 - 6 * n.q * low.B / low.L


def sourceT(n, b):
    return n.B - n.L * (b - n.allowance)


def sourceA(n, low, b):
    return (n.q * (b + (sourceT(n, b) - low.B) / low.L) + n.lowFee) / sourceDen(n, low)


def sourceF(n, low, b):
    return 1 - 6 * sourceA(n, low, b)


def scalarGates(n, low, b):
    a = sourceA(n, low, b)
    t = sourceT(n, b)
    T = t + b
    F = sourceF(n, low, b)
    e = n.allowance
    Lref = Q(49, 100) - KREF * b
    return [sourceDen(n, low), b - 2 * e, a, Q(1, 75) - a, F - T / 2 - 4 * e,
            low.B * F - t - b - 4 * e, 1 - n.q * low.cap,
            n.lowFee - (n.q * low.B / low.L + n.q * low.cap + 4) * e - 10 * e,
            a - 20 * e, Lref, 1 - Lref - Q(1, 2) - KREF * b - 10 * e,
            Q(5, 6) + Q(499, 1000) * Lref - T - 9 * a - n.highFee,
            1 - T - 5 * a - n.highFee, 1 - Q(1, 50) - T - 4 * a - n.highFee,
            1 - Q(1, 50) - T - Q(9, 2) * a - n.highFee, Lref - 7 * a - n.highFee]


def weakCap(n, low, b):
    return low.cap * sourceF(n, low, b) - (low.B * sourceF(n, low, b) - sourceT(n, b)) / low.L


def densityGates(n, low, high, b, nu):
    a = sourceA(n, low, b)
    T = sourceT(n, b) + b
    Sv = b - 2 * n.allowance
    F = sourceF(n, low, b) - n.allowance
    fee = n.highFee
    t = 15 - 6 * nu
    w = 5 - 6 * nu
    H = (a - nu * T) * t + (10 - 60 * a) * nu
    fixed = H + (nu * F / 2 - (1 - nu) * b - fee) * t
    core = H + (Q(5, 6) * F - (1 - nu) * b - fee) * t - 10 * nu * F
    tiny = H + (nu * (F - Q(1, 50)) / 2 - (1 - nu) * b - fee) * t - 10 * nu * Q(1, 50)
    if high is None:
        D2 = 115 - 54 * nu
        D3 = 185 - 138 * nu
        return [H + 3 * nu * w * Sv - fee * t,
                H * D2 + 14 * nu * w * Sv * t + 2 * nu * w * w * F - fee * t * D2,
                H * D3 + 16 * nu * w * w * F - fee * t * D3, fixed, core, tiny, Q(1), Q(1), Q(1)]
    h = high
    D13 = h.L * t - 10
    D4 = 10 + 3 * w
    D23 = h.L * (10 + 3 * w) - (10 + 2 * w)
    return [H + 3 * nu * w * Sv - fee * t,
            H + (2 * nu * w * Sv + nu * w * h.cap * F) - fee * t,
            H * D13 + 2 * nu * w * (h.L - 1) * Sv * t + nu * w * (h.B * t - 10) * F - fee * t * D13,
            H * D4 + nu * w * Sv * t + 2 * nu * w * w * F - fee * t * D4,
            H * D4 + (2 * nu * w * w + nu * w * h.cap * t) * F - fee * t * D4,
            H * D23 + nu * w * (2 * w * (h.L - 1) + h.B * t - 10) * F - fee * t * D23,
            fixed, core, tiny]


def bernstein(f0, f1, fm1, f2, l, r):
    c0 = f0
    c1 = (-f2 + 6 * f1 - 3 * f0 - 2 * fm1) / 6
    c2 = (f1 + fm1 - 2 * f0) / 2
    c3 = (f2 - 3 * f1 + 3 * f0 - fm1) / 6
    a0 = c0 + c1 * l + c2 * l ** 2 + c3 * l ** 3
    a1 = (r - l) * (c1 + 2 * c2 * l + 3 * c3 * l ** 2)
    a2 = (r - l) ** 2 * (c2 + 3 * c3 * l)
    a3 = (r - l) ** 3 * c3
    return [a0, a0 + a1 / 3, a0 + 2 * a1 / 3 + a2 / 3, a0 + a1 + a2 + a3]


def source_valid(n, low, high):
    """Return None if valid, else a short reason."""
    if not (0 < n.B and n.B <= 1 and 1 < n.L and 0 <= n.cap and n.cap < 1):
        return 'node box'
    if not (Q(1, 2) <= n.q and n.q <= Q(3, 4) and n.L < low.L):
        return 'q range or L order'
    x = crossing(n, low)
    if not (0 <= x and x <= n.cap and x <= low.cap):
        return 'crossing'
    if high is not None and not (Q(22, 23) <= high.B and high.B <= 1 and 1 < high.L and 0 <= high.cap and high.cap < 1):
        return 'high box'
    for b in (x, n.cap):  # Lean: ∀ b ∈ [crossing n low, n.cap] (a two-element List)
        g = scalarGates(n, low, b)
        for j, v in enumerate(g):
            if not v > 0:
                return f'scalarGate {j}'
        if not weakCap(n, low, b) >= 0:
            return 'weakCap'
        d = {nu: densityGates(n, low, high, b, Q(nu)) for nu in (0, 1, -1, 2)}
        for j in range(9):
            bs = bernstein(d[0][j], d[1][j], d[-1][j], d[2][j], n.q, Q(3, 4))
            for i, v in enumerate(bs):
                if not v > 0:
                    return f'densityGate {j} bernstein {i}'
    return None


def parse(path):
    sources, valids, other = {}, [], 0
    for line in open(path, encoding='utf8'):
        m = SRC.match(line)
        if m:
            parts = [p.strip() for p in m.group(2).split(',')]
            if len(parts) != 7:
                raise ValueError(f'{path}: {m.group(1)} has {len(parts)} fields')
            sources[m.group(1)] = S([rat(p) for p in parts])
            continue
        m = VALID.match(line)
        if m:
            valids.append((m.group(1), m.group(2), m.group(3), m.group(5)))
        elif line.startswith('theorem valid'):
            other += 1
    return sources, valids, other


def check_file(path):
    t0 = time.time()
    sources, valids, other = parse(path)
    failures = []
    pattern_ok = True
    for name, child, low, high in valids:
        # Every child must use its immediately preceding node as both suppliers.
        idx = int(child[6:])
        if name != 'valid' + child[6:] or low != f'source{idx-1:03d}' or high != low:
            pattern_ok = False
        r = source_valid(sources[child], sources[low], sources[high] if high else None)
        if r:
            failures.append((name, r))
    fees_ok = all(s.allowance == Q(1, 10**17) and s.lowFee == Q(1, 10**12) and s.highFee == Q(1, 10**10)
                  for s in sources.values())
    last = max(sources, key=lambda k: int(k[6:]))
    return {'file': os.path.basename(path), 'transitions': len(valids), 'unparsed_valid_lines': other,
            'failures': failures, 'supplier_pattern_ok': pattern_ok, 'fees_ok': fees_ok,
            'first': sources['source000'].tup(), 'last_name': last, 'last': sources[last].tup(),
            'seconds': round(time.time() - t0, 1)}


def main():
    root, out = sys.argv[1], sys.argv[2]
    gdir = os.path.join(root, 'Graphs')
    files = sorted(os.path.join(gdir, f) for f in os.listdir(gdir) if f.endswith('.lean'))
    with Pool(int(os.environ.get('JOBS', os.cpu_count() or 1))) as pool:
        results = pool.map(check_file, files, chunksize=4)
    families = {}
    for r in results:
        fam = re.match(r'([AB](?:Count|Physical))', r['file']).group(1)
        families.setdefault(fam, []).append(r)
    summary = {}
    for fam, rs in sorted(families.items()):
        rs.sort(key=lambda r: r['file'])
        links = [i for i in range(1, len(rs)) if rs[i]['first'] != rs[i - 1]['last']]
        summary[fam] = {
            'batches': len(rs), 'transitions': sum(r['transitions'] for r in rs),
            'failures': sum(len(r['failures']) for r in rs),
            'unparsed_valid_lines': sum(r['unparsed_valid_lines'] for r in rs),
            'supplier_pattern_ok': all(r['supplier_pattern_ok'] for r in rs),
            'fees_ok': all(r['fees_ok'] for r in rs),
            'broken_links': [rs[i]['file'] for i in links],
            'root': rs[0]['first'], 'terminal': rs[-1]['last'], 'terminal_at': rs[-1]['file'] + ':' + rs[-1]['last_name'],
        }
    report = {'checker': 'independent exact-rational SourceValid re-check (gmpy2 mpq)',
              'summary': summary,
              'total_transitions': sum(s['transitions'] for s in summary.values()),
              'total_failures': sum(s['failures'] for s in summary.values()),
              'failing': [(r['file'], r['failures'][:5]) for r in results if r['failures']],
              'cpu_seconds': round(sum(r['seconds'] for r in results), 1)}
    json.dump(report, open(out, 'w'), indent=1)
    print(json.dumps({k: v for k, v in report.items() if k != 'failing'}, indent=1)[:6000])
    print('failing files:', len(report['failing']))


if __name__ == '__main__':
    main()

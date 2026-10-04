"""S graphics: a frame of primitives, drawn on a line printer (text) or a Tektronix 4014 (SVG)."""
import html
import math

PHOSPHOR = '#7dff9a'


def pretty(lo, hi, n=5):
    """Tick values at 1-2-5 steps covering [lo, hi]."""
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    k0, k1 = math.ceil(lo / step - 1e-9), math.floor(hi / step + 1e-9)
    return [round(k * step, 12) for k in range(k0, k1 + 1)]


def label(t):
    return f'{t:.6g}'


def limits(vals, zero=False):
    lo, hi = min(vals), max(vals)
    if zero:
        lo, hi = min(lo, 0), max(hi, 0)
    if lo == hi:
        lo, hi = lo - 1, hi + 1
    pad = (hi - lo) * 0.04
    return (lo if zero and lo == 0 else lo - pad), hi + pad


class Frame:
    """One plot. Items are kept in data coordinates; devices see normalised [0,1] coordinates."""

    def __init__(self, xs, ys, log='', main='', sub='', xlab='', ylab='', zero=False):
        self.logx, self.logy = 'x' in log, 'y' in log
        self.main, self.sub, self.xlab, self.ylab = main, sub, xlab, ylab
        self.items = []
        tx = [v for v in (self.t(x, self.logx) for x in xs) if v is not None]
        ty = [v for v in (self.t(y, self.logy) for y in ys) if v is not None]
        if not tx or not ty:
            raise ValueError('nothing to plot')
        self.xlim, self.ylim = limits(tx), limits(ty, zero)

    @staticmethod
    def t(v, log):
        if v is None or not math.isfinite(v):
            return None
        if log:
            return math.log10(v) if v > 0 else None
        return v

    def norm(self, x, y):
        x, y = self.t(x, self.logx), self.t(y, self.logy)
        if x is None or y is None:
            return None
        (x0, x1), (y0, y1) = self.xlim, self.ylim
        return (x - x0) / (x1 - x0), (y - y0) / (y1 - y0)

    def ticks(self, axis):
        lo, hi = self.xlim if axis == 'x' else self.ylim
        log = self.logx if axis == 'x' else self.logy
        if log and math.floor(hi) - math.ceil(lo) >= 1:
            ts = range(math.ceil(lo), math.floor(hi) + 1)
            return [((t - lo) / (hi - lo), label(10 ** t)) for t in ts]
        return [((t - lo) / (hi - lo), label(10 ** t if log else t))
                for t in pretty(lo, hi) if lo <= t <= hi]

    def prims(self):
        """('seg', u1, v1, u2, v2) clipped to the plot box, ('pt', u, v, ch), ('txt', u, v, s)."""
        out = []
        for it in self.items:
            kind = it[0]
            if kind in ('pts', 'text'):
                for x, y, s in zip(it[1], it[2], it[3]):
                    p = self.norm(x, y)
                    if p and 0 <= p[0] <= 1 and 0 <= p[1] <= 1:
                        out.append(('pt' if kind == 'pts' else 'txt', *p, s))
            elif kind == 'line':
                pts = [self.norm(x, y) for x, y in zip(it[1], it[2])]
                for p, q in zip(pts, pts[1:]):
                    if p and q:
                        seg = clip(*p, *q)
                        if seg:
                            out.append(('seg', *seg))
            elif kind == 'abline':          # y = a + b x across the whole box (linear axes)
                a, b = it[1], it[2]
                (x0, x1), (y0, y1) = self.xlim, self.ylim
                seg = clip(0, (a + b * x0 - y0) / (y1 - y0), 1, (a + b * x1 - y0) / (y1 - y0))
                if seg:
                    out.append(('seg', *seg))
            elif kind in ('h', 'v'):
                lo, hi = self.ylim if kind == 'h' else self.xlim
                w = self.t(it[1], self.logy if kind == 'h' else self.logx)
                if w is not None and lo <= w <= hi:
                    w = (w - lo) / (hi - lo)
                    out.append(('seg', 0, w, 1, w) if kind == 'h' else ('seg', w, 0, w, 1))
        return out


def clip(u1, v1, u2, v2):
    """Liang-Barsky clip of a segment to the unit square."""
    t0, t1, du, dv = 0.0, 1.0, u2 - u1, v2 - v1
    for p, q in ((-du, u1), (du, 1 - u1), (-dv, v1), (dv, 1 - v1)):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return None
    return u1 + t0 * du, v1 + t0 * dv, u1 + t1 * du, v1 + t1 * dv


def printer(fr, W=80, P=17):
    """Line-printer plot: dot borders, '+' ticks, vertical y label (manual p. 2-23)."""
    yt, xt = fr.ticks('y'), fr.ticks('x')
    tw = max((len(s) for _, s in yt), default=1)
    L, R = tw + 3, W - 2              # border columns
    T, B = 1, P + 2                   # border rows
    g = [[' '] * W for _ in range(P + 6)]
    nw = R - L - 1

    def col(u):
        return L + 1 + round(u * (nw - 1))

    def row(v):
        return T + 1 + round((1 - v) * (P - 1))

    def put(r, c, ch):
        if T < r < B and L < c < R:
            g[r][c] = ch

    def puts(r, c, s):
        for k, ch in enumerate(s):
            if 0 <= c + k < W:
                g[r][c + k] = ch

    for c in range(L, R + 1):
        g[T][c] = g[B][c] = '.'
    for r in range(T, B + 1):
        g[r][L] = g[r][R] = '.'
    for v, s in yt:
        r = row(v)
        g[r][L] = '+'
        puts(r, L - 1 - len(s), s)
    end = -1
    for u, s in xt:
        c = col(u)
        g[B][c] = '+'
        start = c - len(s) // 2
        if start > end:
            puts(B + 1, start, s)
            end = start + len(s)
    prims = fr.prims()
    for p in prims:
        if p[0] == 'seg':
            r1, c1, r2, c2 = row(p[2]), col(p[1]), row(p[4]), col(p[3])
            dr, dc = r2 - r1, c2 - c1
            if dr == 0:
                ch = '-'
            elif dc == 0 or abs(dc) < abs(dr) / 2:
                ch = '|'
            elif abs(dc) > 4 * abs(dr):
                ch = '-'
            else:
                ch = '/' if (dc > 0) == (dr < 0) else '\\'
            n = max(abs(dr), abs(dc))
            for k in range(n + 1):
                put(r1 + round(dr * k / n) if n else r1, c1 + round(dc * k / n) if n else c1, ch)
    for p in prims:
        if p[0] == 'txt':
            s = str(p[3])
            for k, ch in enumerate(s):
                put(row(p[2]), col(p[1]) - len(s) // 2 + k, ch)
    for p in prims:
        if p[0] == 'pt':
            put(row(p[2]), col(p[1]), p[3][:1] or '*')
    puts(0, (W - len(fr.main)) // 2, fr.main)
    mid = (L + R) // 2
    puts(B + 2, mid - len(fr.xlab) // 2, fr.xlab)
    puts(B + 3, mid - len(fr.sub) // 2, fr.sub)
    ylab = fr.ylab[:P]
    for k, ch in enumerate(ylab):
        g[T + 1 + (P - len(ylab)) // 2 + k][0] = ch
    lines = [''.join(r).rstrip() for r in g]
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def svg(fr, W=1024, H=780):
    """Tektronix 4014 frame (1024 x 780 addressable points) as a single-line SVG."""
    L, R, T, B = 120, 984, 80, 640
    X = lambda u: round(L + u * (R - L), 1)
    Y = lambda v: round(B - v * (B - T), 1)
    e = html.escape
    path, text = [f'M{L} {T}H{R}V{B}H{L}Z'], []
    for v, s in fr.ticks('y'):
        path.append(f'M{L - 10} {Y(v)}H{L}')
        text.append(f'<text x="{L - 16}" y="{Y(v)}" text-anchor="end" dominant-baseline="central">{e(s)}</text>')
    for u, s in fr.ticks('x'):
        path.append(f'M{X(u)} {B}V{B + 10}')
        text.append(f'<text x="{X(u)}" y="{B + 34}" text-anchor="middle">{e(s)}</text>')
    for p in fr.prims():
        if p[0] == 'seg':
            path.append(f'M{X(p[1])} {Y(p[2])}L{X(p[3])} {Y(p[4])}')
        else:
            text.append(f'<text x="{X(p[1])}" y="{Y(p[2])}" text-anchor="middle" '
                        f'dominant-baseline="central">{e(str(p[3]))}</text>')
    mid = (L + R) // 2
    text += [f'<text x="{W // 2}" y="44" font-size="28" text-anchor="middle">{e(fr.main)}</text>',
             f'<text x="{mid}" y="{B + 80}" text-anchor="middle">{e(fr.xlab)}</text>',
             f'<text x="{mid}" y="{B + 112}" text-anchor="middle">{e(fr.sub)}</text>',
             f'<text transform="translate(36 {(T + B) // 2}) rotate(-90)" text-anchor="middle">{e(fr.ylab)}</text>']
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'font-family="monospace" font-size="20">'
            f'<path d="{"".join(path)}" fill="none" stroke="{PHOSPHOR}" stroke-width="1.6"/>'
            f'<g fill="{PHOSPHOR}">{"".join(text)}</g></svg>')


def osc(svg_text, erase=False):
    """Private OSC sequence for the 4014 beside the terminal. Like a storage tube, the picture
    only grows; erase=True first clears the whole screen with the 4014's green flash."""
    return '\x1b]1979;' + ('E;' if erase else '') + svg_text + '\x07'


BLANK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 780"/>'


def stem(vals):
    """Tukey stem-and-leaf display in the manual's format (p. 2-21)."""
    v = sorted(vals)
    n = len(v)

    def med(a):
        m = len(a) // 2
        return a[m] if len(a) % 2 else (a[m - 1] + a[m]) / 2

    median = med(v)
    lo_h, hi_h = med(v[:(n + 1) // 2]), med(v[n // 2:])
    span = v[-1] - v[0]
    p = math.floor(math.log10(span)) if span > 0 else (math.floor(math.log10(abs(v[0]))) if v[0] else 0)
    leaf_unit = 10.0 ** (p - 1)

    def key(x):
        t = round(x / leaf_unit)
        neg = x < 0
        return (neg, abs(t) // 10), abs(t) % 10

    def order(k):
        return -k[1] - 0.5 if k[0] else k[1]

    stems = {}
    for x in v:
        k, leaf = key(x)
        stems.setdefault(k, []).append(leaf)
    ks = sorted(stems, key=order)
    neg = [k[1] for k in ks if k[0]]
    pos = [k[1] for k in ks if not k[0]]
    allk = []
    if neg:
        allk += [(True, s) for s in range(max(neg), (-1 if pos else min(neg) - 1), -1)]
    if pos:
        allk += [(False, s) for s in range(0 if neg else min(pos), max(pos) + 1)]
    mk = key(median)[0]
    counts = [len(stems.get(k, [])) for k in allk]
    m_i = allk.index(mk) if mk in allk else -1
    out = [f'N = {n:>3}   Median = {median:>9.3f}   Hinges = {lo_h:>9.3f} {hi_h:.3f}', '']
    if p == 0:
        out.append('   Decimal point is at the colon')
    else:
        side = 'right' if p > 0 else 'left'
        out.append(f'   Decimal point is {abs(p)} place(s) to the {side} of the colon')
    out.append('')
    for i, k in enumerate(allk):
        leaves = sorted(stems.get(k, []), reverse=k[0])
        if i == m_i:
            depth = ''
        elif i < m_i:
            depth = sum(counts[:i + 1])
        else:
            depth = sum(counts[i:])
        name = ('-' if k[0] else '') + str(k[1])
        out.append(f'{depth:>6}{counts[i]:>7}{name:>5} : {"".join(map(str, leaves))}')
    return '\n'.join(out)

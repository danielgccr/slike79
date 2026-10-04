"""eqn and troff, for the 1982 film's typesetting demonstration: `eqn file | troff`.

As in the real tools, eqn does the two-dimensional layout and writes plain troff with
motion escapes (\\v \\h \\l \\s \\f \\( ); troff fills, adjusts and sets the page. The
"phototypesetter" here is an SVG proof the browser shows over the terminal.
"""
import html
import re

# troff special-character names -> what the typesetter prints
SPECIAL = {
    '*a': 'α', '*b': 'β', '*g': 'γ', '*d': 'δ', '*e': 'ε', '*z': 'ζ', '*y': 'η', '*h': 'θ', '*i': 'ι',
    '*k': 'κ', '*l': 'λ', '*m': 'μ', '*n': 'ν', '*c': 'ξ', '*o': 'ο', '*p': 'π', '*r': 'ρ', '*s': 'σ',
    '*t': 'τ', '*u': 'υ', '*f': 'φ', '*x': 'χ', '*q': 'ψ', '*w': 'ω',
    '*G': 'Γ', '*D': 'Δ', '*H': 'Θ', '*L': 'Λ', '*C': 'Ξ', '*P': 'Π', '*S': 'Σ', '*U': 'Υ', '*F': 'Φ',
    '*Q': 'Ψ', '*W': 'Ω',
    'if': '∞', 'pd': '∂', 'sr': '√', 'is': '∫', 'pl': '+', 'mi': '−', 'eq': '=', 'mu': '×', '+-': '±',
    '<=': '≤', '>=': '≥', '!=': '≠', 'ap': '≈', '->': '→', '<-': '←', 'cu': '∪', 'ca': '∩', 'bu': '•',
    'em': '—', 'de': '°', 'gr': '∇', 'ul': '_', 'sc': '§', 'dg': '†', 'co': '©',
}
NAMES = {v: k for k, v in SPECIAL.items()}
NAMES['Σ'] = '*S'       # the reverse map must be unambiguous for these
NAMES['Π'] = '*P'

WIDE_SYMBOLS = {'Σ': .72, 'Π': .72, '∫': .4, '√': .55, '∞': .72, '→': .8, '←': .8}


# Advance widths of ASCII 32-126 in thousandths of an em: Times metrics, read from Liberation
# Serif (metric-compatible), so the proof's textLength squeezes or stretches no glyph.
TIMES = {
    'R': [250, 333, 408, 500, 500, 833, 778, 180, 333, 333, 500, 564, 250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 278, 278, 564, 564, 564, 444, 921, 722, 667, 667, 722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722, 722, 556, 722, 667, 556, 611, 722, 722, 944, 722, 722, 611, 333, 278, 333, 469, 500, 333, 444, 500, 444, 500, 444, 333, 500, 500, 278, 278, 500, 278, 778, 500, 500, 500, 500, 333, 389, 278, 500, 500, 722, 500, 500, 444, 480, 200, 480, 541],
    'I': [250, 333, 420, 500, 500, 833, 778, 214, 333, 333, 500, 675, 250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 333, 333, 675, 675, 675, 500, 920, 611, 611, 667, 722, 611, 611, 722, 722, 333, 444, 667, 556, 833, 667, 722, 611, 722, 611, 500, 556, 722, 611, 833, 611, 556, 556, 389, 278, 389, 422, 500, 333, 500, 500, 444, 500, 444, 278, 500, 500, 278, 278, 444, 278, 722, 500, 500, 500, 500, 389, 389, 278, 500, 444, 667, 444, 444, 389, 400, 275, 400, 541],
    'B': [250, 333, 555, 500, 500, 1000, 833, 278, 333, 333, 500, 570, 250, 333, 250, 278, 500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 333, 333, 570, 570, 570, 500, 930, 722, 667, 722, 722, 667, 611, 778, 778, 389, 500, 778, 667, 944, 722, 778, 611, 778, 722, 556, 667, 722, 722, 1000, 722, 722, 667, 333, 278, 333, 581, 500, 333, 500, 556, 444, 556, 444, 333, 500, 556, 278, 333, 556, 278, 833, 556, 500, 556, 556, 444, 389, 333, 556, 500, 722, 500, 500, 444, 394, 220, 394, 520],
}


FONTS = {'R': 'R', 'I': 'I', 'B': 'B', 'C': 'C', 'CW': 'C'}


def width(text, size, font='R'):
    """Set width in points. eqn and troff share this, and the proof forces each run to it."""
    if font == 'C':
        return 0.6 * size * len(text)     # constant width
    metrics = TIMES.get(font, TIMES['R'])
    w = 0.0
    for ch in text:
        if ' ' <= ch <= '~':
            w += metrics[ord(ch) - 32] / 1000 * size
            continue
        if ch == ' ':
            k = .25
        elif ch in WIDE_SYMBOLS:
            k = WIDE_SYMBOLS[ch]
        elif ch in 'ijlt.,;:!|\'`':
            k = .28
        elif ch in '()[]{}/fr':
            k = .34
        elif ch in 'mwMW':
            k = .78
        elif ch.isupper():
            k = .66
        elif ch.isdigit():
            k = .5
        elif ch in '=+−±×≤≥≠≈':
            k = .56
        else:
            k = .46
        w += k * size
    return w


# ---------------------------------------------------------------- troff

def amount(arg, size, default='p'):
    m = re.fullmatch(r'\s*([-+]?(?:\d+\.?\d*|\.\d+))([picmnvu]?)\s*', arg)
    if not m:
        return 0.0
    unit = m.group(2) or default
    scale = {'p': 1, 'i': 72, 'c': 72 / 2.54, 'm': size, 'n': size / 2, 'v': 1.2 * size, 'u': 1 / 6}[unit]
    return float(m.group(1)) * scale


class State:
    def __init__(self):
        self.size = self.base = 10.0
        self.font = self.prev = 'R'


def render(s, st):
    """Set one word (or one no-fill line): returns items at x from its start, y down from the baseline,
    and the horizontal advance. Font and size changes persist in st, as they do in troff."""
    items, buf = [], []
    x = y = 0.0
    i = 0

    def flush():
        nonlocal x
        if buf:
            t = ''.join(buf)
            w = width(t, st.size, st.font)
            items.append(('t', x, y, t, st.font, st.size, w))
            x += w
            buf.clear()

    while i < len(s):
        c = s[i]
        if c != '\\' or i + 1 >= len(s):
            buf.append(c)
            i += 1
            continue
        e = s[i + 1]
        i += 2
        if e == 'f':
            flush()
            if s[i:i + 1] == '(':
                name, i = s[i + 1:i + 3], i + 3
            else:
                name, i = s[i:i + 1], i + 1
            name = st.prev if name == 'P' else name
            st.prev, st.font = st.font, FONTS.get(name, 'R')
        elif e == 's':
            flush()
            m = re.match(r"'([^']*)'|0|[1-3]\d|[4-9]|[+-]\d", s[i:])
            if m:
                i += m.end()
                arg = m.group(1) if m.group(1) is not None else m.group()
                if arg in ('0', ''):
                    st.size = st.base
                elif arg[0] in '+-':
                    st.size = max(1.0, st.size + float(arg))
                else:
                    st.size = max(1.0, float(arg))
        elif e in 'vhl':
            m = re.match(r"'([^']*)'", s[i:])
            if not m:
                continue
            i += m.end()
            amt = amount(m.group(1), st.size)
            flush()
            if e == 'v':
                y += amt
            elif e == 'h':
                x += amt
            else:
                items.append(('r', x, y, amt, st.size))
                x += amt
        elif e in 'ud':
            flush()
            y += (st.size if e == 'd' else -st.size) * 0.5
        elif e == '(':
            buf.append(SPECIAL.get(s[i:i + 2], '?'))
            i += 2
        elif e == 'e':
            buf.append('\\')
        elif e == '-':
            buf.append('−')
        elif e == '&':
            pass
        elif e in '|^':
            flush()
            x += st.size / (6 if e == '|' else 12)
        else:
            buf.append(e)          # '\ ' is an unpaddable space
    flush()
    return items, x


def shifted(items, dx, dy=0.0):
    return [(it[0], it[1] + dx, it[2] + dy, *it[3:]) for it in items]


WORDS = re.compile(r'(?<!\\)[ \t]+')             # \  (backslash-space) is not a break
STRING = re.compile(r'\\\*(?:\((..)|(.))')
MS = re.compile(r'^\.(TL|AU|AI|AB|AE|SH|NH|PP|LP|DS|DE|B|I|R)(?:\s+(.*))?$')


def interpolate(line, strings):
    r"""\*x and \*(xx: troff strings defined with .ds."""
    return STRING.sub(lambda m: strings.get(m.group(1) or m.group(2), ''), line)


def define_string(args_text, strings):
    name, _, value = args_text.strip().partition(' ')
    strings[name] = value.lstrip().removeprefix('"')


def ms(src, nroff=False):
    """The -ms macros (Lesk, shipped with V7), as plain requests both formatters understand:
    title, author, institution, abstract, numbered and unnumbered headings, paragraphs, displays."""
    out, mode, buf, nh = [], None, [], 0
    gap = '.sp' if nroff else '.sp 0.5'

    def flush():
        nonlocal mode, buf
        if mode == 'TL':
            out.extend(['.sp 3' if nroff else '.sp 0.5i', '.ft B', *([] if nroff else ['.ps 12']),
                        f'.ce {len(buf)}', *buf, '.ft R', *([] if nroff else ['.ps 10'])])
        elif mode == 'AU':
            out.extend(['.sp', '.ft I', f'.ce {len(buf)}', *buf, '.ft R'])
        elif mode == 'AI':
            out.extend([f'.ce {len(buf)}', *buf])
        elif mode in ('SH', 'NH') and buf:
            if mode == 'NH':
                buf = [f'{nh}.\\ \\ ' + buf[0]] + buf[1:]
            out.extend(['.sp', '.ft B', *buf, '.ft R', '.br'])
        mode, buf = None, []

    for line in src.split('\n'):
        m = MS.match(line)
        if not m:
            (buf if mode else out).append(line)
            continue
        flush()
        mac, arg = m.group(1), (m.group(2) or '').strip().strip('"')
        if mac in ('TL', 'AU', 'AI', 'SH', 'NH'):
            mode = mac
            nh += mac == 'NH'
        elif mac == 'AB':
            out.extend(['.sp 2' if nroff else '.sp', '.ce', '\\fIABSTRACT\\fR', gap, '.in +5n', '.ll -5n'])
        elif mac == 'AE':
            out.extend(['.in -5n', '.ll +5n', '.sp'])
        elif mac == 'PP':
            out.extend([gap, '.ti +5n'])
        elif mac == 'LP':
            out.append(gap)
        elif mac == 'DS':
            out.extend([gap, '.nf', '.in +5n'])
        elif mac == 'DE':
            out.extend(['.in -5n', '.fi', gap])
        else:                                          # .B .I .R: a word in that font, or switch to it
            out.append(f'\\f{mac}{arg}\\fR' if arg else f'.ft {mac}')
    flush()
    return '\n'.join(out)


class Layout:
    """What troff and nroff share: filling, adjusting, centring, indents, strings."""

    def __init__(self, ll, unit):
        self.ll, self.unit = ll, unit       # line length; points per en (troff) or 1 char (nroff)
        self.indent, self.ti, self.fill, self.center, self.strings = 0.0, None, True, 0, {}

    def length(self, arg, current, size):
        if not arg:
            return None
        rel = arg[0] in '+-'
        v = self.amount(arg.lstrip('+-'), size)
        return current + (v if arg[0] == '+' else -v) if rel else v

    def x0(self):
        return self.ti if self.ti is not None else self.indent


def troff(src, macros=False):
    """Format troff input; returns an SVG page proof."""
    if macros:
        src = ms(src)
    st = State()
    lay = Layout(468.0, 5.0)                   # 6.5 inch line
    lay.amount = lambda a, size: amount(a, size, 'n')
    out = []                                   # ('line', items, vs) | ('space', points)
    line, lw = [], 0.0

    def emit(adjust):
        nonlocal line, lw
        if not line:
            return
        x0 = lay.x0()
        room = lay.ll - x0
        extra = (room - lw) / (len(line) - 1) if adjust and len(line) > 1 and lw < room else 0.0
        items, x = [], x0
        for k, (its, w, sp) in enumerate(line):
            if k:
                x += sp + extra
            items += shifted(its, x)
            x += w
        out.append(('line', items, 1.2 * st.size))
        line, lw, lay.ti = [], 0.0, None

    for raw in src.split('\n'):
        raw = interpolate(raw, lay.strings)
        if raw[:1] in ('.', "'"):
            req, *args = raw[1:].split() or ['']
            a0 = args[0] if args else ''
            if req == 'br':
                emit(False)
            elif req == 'sp':
                emit(False)
                out.append(('space', amount(a0, st.size, 'v') if args else 1.2 * st.size))
            elif req == 'ce':
                emit(False)
                lay.center = int(a0) if a0.isdigit() else 1
            elif req == 'ft':
                f = a0 or 'P'
                st.prev, st.font = st.font, (st.prev if f == 'P' else FONTS.get(f, 'R'))
            elif req == 'ps':
                st.size = st.base = max(1.0, float(a0)) if re.fullmatch(r'\d+(\.\d+)?', a0) else 10.0
            elif req in ('nf', 'fi'):
                emit(False)
                lay.fill = req == 'fi'
            elif req == 'll' and args:
                lay.ll = max(72.0, lay.length(a0, lay.ll, st.size))
            elif req == 'in':
                emit(False)
                lay.indent = max(0.0, lay.length(a0, lay.indent, st.size) or 0.0)
            elif req == 'ti':
                emit(False)
                lay.ti = max(0.0, lay.length(a0, lay.indent, st.size) or 0.0)
            elif req == 'ds':
                define_string(raw[3:], lay.strings)
            elif req == 'bp':
                emit(False)
                out.append(('space', 36.0))
            continue                           # unknown requests are ignored, as troff does
        if lay.center or not lay.fill:
            emit(False)
            items, w = render(raw, st)
            x = lay.indent + (lay.ll - lay.indent - w) / 2 if lay.center else lay.x0()
            out.append(('line', shifted(items, x), 1.2 * st.size))
            lay.center, lay.ti = max(0, lay.center - 1), None
            continue
        if not raw.strip():
            emit(False)
            out.append(('space', 1.2 * st.size))
            continue
        if raw[0] in ' \t':
            emit(False)
        for word in WORDS.split(raw.strip()):
            its, w = render(word, st)
            sp = width(' ', st.size)
            if line and lw + sp + w > lay.ll - lay.x0():
                emit(True)
            if line:
                lw += sp
            line.append((its, w, sp))
            lw += w
    emit(False)
    return page(out)


# ---------------------------------------------------------------- nroff

ASCII = {'−': '-', '≤': '<=', '≥': '>=', '≠': '!=', '±': '+-', '→': '->', '←': '<-', '×': 'x', '∞': 'inf',
         '∂': 'd', '≈': '~', '≡': '==', '·': '.', '…': '...', '′': "'", 'Σ': 'SUM', 'Π': 'PROD', '∫': 'INT',
         '√': 'sqrt', '∪': 'U', '∩': '^', '∇': 'grad', '—': '--', '•': 'o', '°': 'o', '§': 'S', '†': '+',
         '©': '(c)', '_': '_'}


def nroff(src, macros=False):
    """The terminal formatter: the same requests as troff, set in fixed-width characters, with
    bold struck twice and italics underlined (char, backspace, char) as nroff did."""
    if macros:
        src = ms(src, nroff=True)
    lay = Layout(65, 1)
    lay.amount = lambda a, size: char_amount(a)
    font, prev, out = ['R'], ['R'], []
    line, lw = [], 0

    def render_word(text):
        cells, w, i = [], 0, 0
        while i < len(text):
            c = text[i]
            if c == '\\' and i + 1 < len(text):
                e, i = text[i + 1], i + 2
                if e == 'f':
                    name, i = (text[i + 1:i + 3], i + 3) if text[i:i + 1] == '(' else (text[i:i + 1], i + 1)
                    name = prev[0] if name == 'P' else name
                    prev[0], font[0] = font[0], FONTS.get(name, 'R')
                    continue
                if e == 's':
                    m = re.match(r"'[^']*'|0|[1-3]\d|[4-9]|[+-]\d", text[i:])
                    i += m.end() if m else 0
                    continue
                if e in 'vhlL':
                    m = re.match(r"'[^']*'", text[i:])
                    i += m.end() if m else 0
                    continue
                if e in 'ud&|^':
                    continue
                if e == '(':
                    ch = ASCII.get(SPECIAL.get(text[i:i + 2], '?'), SPECIAL.get(text[i:i + 2], '?'))
                    ch = GREEK_NAMES.get(ch, ch)
                    i += 2
                else:
                    ch = {'e': '\\', '-': '-', '0': ' '}.get(e, e)
            else:
                ch, i = c, i + 1
            for k in ch:
                if font[0] == 'B' and k.strip():
                    cells.append(k + '\b' + k)
                elif font[0] == 'I' and k.isalnum():
                    cells.append('_\b' + k)
                else:
                    cells.append(k)
                w += 1
        return ''.join(cells), w

    def emit(adjust):
        nonlocal line, lw
        if not line:
            return
        x0 = int(lay.x0())
        gaps = len(line) - 1
        extra = max(0, int(lay.ll) - x0 - lw) if adjust and gaps else 0
        text = ''
        for k, (word, w) in enumerate(line):
            if k:
                text += ' ' * (1 + extra // gaps + (1 if k <= extra % gaps else 0))
            text += word
        out.append(' ' * x0 + text)
        line, lw, lay.ti = [], 0, None

    for raw in src.split('\n'):
        raw = interpolate(raw, lay.strings)
        if raw[:1] in ('.', "'"):
            req, *args = raw[1:].split() or ['']
            a0 = args[0] if args else ''
            if req == 'br':
                emit(False)
            elif req == 'sp':
                emit(False)
                out.extend([''] * (int(char_amount(a0, 'v') + 0.5) if args else 1))
            elif req == 'ce':
                emit(False)
                lay.center = int(a0) if a0.isdigit() else 1
            elif req == 'ft':
                f = a0 or 'P'
                prev[0], font[0] = font[0], (prev[0] if f == 'P' else FONTS.get(f, 'R'))
            elif req in ('nf', 'fi'):
                emit(False)
                lay.fill = req == 'fi'
            elif req == 'll' and args:
                lay.ll = max(20, lay.length(a0, lay.ll, 10))
            elif req == 'in':
                emit(False)
                lay.indent = max(0, lay.length(a0, lay.indent, 10) or 0)
            elif req == 'ti':
                emit(False)
                lay.ti = max(0, lay.length(a0, lay.indent, 10) or 0)
            elif req == 'ds':
                define_string(raw[3:], lay.strings)
            elif req == 'bp':
                emit(False)
                out.extend(['', '', ''])
            continue
        if lay.center or not lay.fill:
            emit(False)
            text, w = render_word(raw)
            x = int(lay.indent + (lay.ll - lay.indent - w) // 2) if lay.center else int(lay.x0())
            out.append(' ' * max(0, x) + text)
            lay.center, lay.ti = max(0, lay.center - 1), None
            continue
        if not raw.strip():
            emit(False)
            out.append('')
            continue
        if raw[0] in ' \t':
            emit(False)
        for word in WORDS.split(raw.strip()):
            text, w = render_word(word)
            if line and lw + 1 + w > lay.ll - lay.x0():
                emit(True)
            if line:
                lw += 1
            line.append((text, w))
            lw += w
    emit(False)
    return '\n'.join(line.rstrip() for line in out) + '\n'


def char_amount(arg, default='n'):
    """nroff units: a character is an en or an em; 10 to the inch; 6 lines to the inch."""
    m = re.fullmatch(r'\s*([-+]?(?:\d+\.?\d*|\.\d+))([picmnvu]?)\s*', arg)
    if not m:
        return 0
    unit = m.group(2) or default
    return float(m.group(1)) * {'m': 1, 'n': 1, 'i': 10 if default != 'v' else 6, 'c': 4, 'p': 1 / 7,
                                'v': 1, 'u': 1 / 24}[unit]


def page(out, left=72.0, top=72.0):
    y, body = top, []
    for kind, *rest in out:
        if kind == 'space':
            y += rest[0]
            continue
        items, vs = rest
        tops = [it[2] - 0.75 * it[5] for it in items if it[0] == 't'] + [it[2] - 2 for it in items if it[0] == 'r']
        bots = [it[2] + 0.25 * it[5] for it in items if it[0] == 't'] + [it[2] + 2 for it in items if it[0] == 'r']
        y += max(-min(tops, default=0), 0.8 * vs)
        base = y
        y += max(max(bots, default=0), 0.2 * vs)
        for it in items:
            if it[0] == 't':
                _, x, dy, t, font, size, w = it
                if not t.strip():
                    continue
                style = (' font-style="italic"' if font == 'I' else ' font-weight="bold"' if font == 'B'
                         else ' font-family="Courier New, Courier, Liberation Mono, monospace"' if font == 'C' else '')
                body.append(f'<text xml:space="preserve" x="{left + x:.2f}" y="{base + dy:.2f}" font-size="{size:.2f}"{style} '
                            f'textLength="{w:.2f}" lengthAdjust="spacingAndGlyphs">{html.escape(t)}</text>')
            else:
                _, x, dy, length, size = it
                th = max(0.4, 0.045 * size)
                body.append(f'<rect x="{left + x:.2f}" y="{base + dy - th / 2:.2f}" width="{abs(length):.2f}" '
                            f'height="{th:.2f}"/>')
    h = y + top
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" style="white-space:pre" viewBox="0 0 612 {h:.0f}" '
            f'width="612" height="{h:.0f}" '
            f'font-family="Times New Roman, Times, Tinos, Liberation Serif, serif" fill="#1d1c1a">'
            f'<rect width="612" height="{h:.0f}" fill="#fbfaf5"/>{"".join(body)}</svg>')


def osc(svg_text):
    """Private OSC sequence: the page shows the proof as if it came off the phototypesetter."""
    return '\x1b]1980;' + svg_text + '\x07'


# ---------------------------------------------------------------- eqn

GREEK = {name: SPECIAL[code] for name, code in [
    ('alpha', '*a'), ('beta', '*b'), ('gamma', '*g'), ('delta', '*d'), ('epsilon', '*e'), ('zeta', '*z'),
    ('eta', '*y'), ('theta', '*h'), ('iota', '*i'), ('kappa', '*k'), ('lambda', '*l'), ('mu', '*m'),
    ('nu', '*n'), ('xi', '*c'), ('omicron', '*o'), ('pi', '*p'), ('rho', '*r'), ('sigma', '*s'),
    ('tau', '*t'), ('upsilon', '*u'), ('phi', '*f'), ('chi', '*x'), ('psi', '*q'), ('omega', '*w'),
    ('GAMMA', '*G'), ('DELTA', '*D'), ('THETA', '*H'), ('LAMBDA', '*L'), ('XI', '*C'), ('PI', '*P'),
    ('SIGMA', '*S'), ('UPSILON', '*U'), ('PHI', '*F'), ('PSI', '*Q'), ('OMEGA', '*W')]}
SYMBOLS = {'inf': '∞', 'partial': '∂', 'times': '×', 'approx': '≈', 'grad': '∇', 'del': '∇', '...': '…',
           'cdot': '·', 'prime': '′'}
BIGOPS = {'sum': 'Σ', 'prod': 'Π', 'int': '∫', 'union': '∪', 'inter': '∩'}
FUNCS = {'sin', 'cos', 'tan', 'log', 'ln', 'exp', 'lim', 'max', 'min', 'det', 'arg', 'sinh', 'cosh', 'tanh'}
OPS = {'->': '→', '<-': '←', '<=': '≤', '>=': '≥', '!=': '≠', '+-': '±', '==': '≡',
       '+': '+', '-': '−', '=': '=', '<': '<', '>': '>'}
RELATIONS = set('=<>→←≤≥≠≡≈')
GREEK_NAMES = {v: k for k, v in GREEK.items()}


class Box:
    def __init__(self, w=0.0, h=0.0, d=0.0, items=()):
        self.w, self.h, self.d, self.items = w, h, d, list(items)


def text(t, font, size):
    tt = ''.join('\\(' + NAMES[ch] if ch in NAMES else '\\ ' if ch == ' ' else '\\e' if ch == '\\' else ch
                 for ch in t)
    w = width(t, size, font)
    return Box(w, 0.7 * size, 0.22 * size, [('t', 0.0, 0.0, tt, font, size, w)])


def hcat(boxes):
    b, x = Box(), 0.0
    for c in boxes:
        b.items += shifted(c.items, x)
        x += c.w
        b.h, b.d = max(b.h, c.h), max(b.d, c.d)
    b.w = x
    return b


def padded(box, pad):
    return Box(box.w + 2 * pad, box.h, box.d, shifted(box.items, pad))


def word(wd, size, lay):
    text, hcat, padded = lay.text, lay.hcat, lay.padded
    if wd in GREEK:
        return text(GREEK[wd], 'R', size)
    if wd in SYMBOLS:
        return text(SYMBOLS[wd], 'R', size)
    if wd in FUNCS:
        return text(wd, 'R', size)
    parts, i = [], 0
    while i < len(wd):
        two = wd[i:i + 2]
        op = two if two in OPS else wd[i] if wd[i] in OPS else None
        if op:
            sym = OPS[op]
            parts.append(padded(text(sym, 'R', size), (0.2 if sym in RELATIONS else 0.12) * size))
            i += len(op)
            continue
        j = i + 1
        if wd[i].isalpha():
            while j < len(wd) and wd[j].isalpha():
                j += 1
            parts.append(text(wd[i:j], 'I', size))
        elif wd[i].isdigit() or wd[i] == '.':
            while j < len(wd) and (wd[j].isdigit() or wd[j] == '.'):
                j += 1
            parts.append(text(wd[i:j], 'R', size))
        else:
            parts.append(text(wd[i], 'R', size))
        i = j
    return hcat(parts)


def tokens(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in '{}~^':
            out.append(c)
            i += 1
        elif c == '"':
            j = s.find('"', i + 1)
            j = len(s) if j < 0 else j
            out.append(('"', s[i + 1:j]))
            i = j + 1
        else:
            j = i
            while j < len(s) and not s[j].isspace() and s[j] not in '{}~^"':
                j += 1
            out.append(s[i:j])
            i = j
    return out


class Eqn:
    """Parser and layout for the eqn language: sub sup over sqrt from to left right roman italic bold,
    and the diacriticals bar and under. Layout goes through the methods below, which neqn overrides."""

    def __init__(self, src):
        self.t, self.i = tokens(src), 0

    # -- layout primitives (typeset: points, items for troff motions)
    def text(self, t, font, size):
        return text(t, font, size)

    def hcat(self, boxes):
        return hcat(boxes)

    def padded(self, box, pad):
        return padded(box, pad)

    def empty(self):
        return Box()

    def space(self, size, wide):
        return Box((0.28 if wide else 0.12) * size)

    def refont(self, b, f):
        b.items = [(*it[:4], f, *it[5:]) if it[0] == 't' else it for it in b.items]
        return b

    def bigop(self, name, size):
        return text(BIGOPS[name], 'R', size * (1.6 if name == 'int' else 1.4))

    def overline(self, b, size, under):
        y = -(b.d + 0.1 * size) if under else b.h + 0.1 * size
        return Box(b.w, b.h if under else y + 0.06 * size, -y + 0.06 * size if under else b.d,
                   b.items + [('r', 0.0, y, b.w, size)])

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self):
        t = self.peek()
        self.i += 1
        return t

    def seq(self, size, stop=()):
        parts = []
        while (t := self.peek()) is not None and t not in stop:
            if t == 'over':                    # binds the boxes either side of it, left to right
                self.next()
                num = parts.pop() if parts else self.empty()
                parts.append(self.fraction(num, self.scripted(size), size))
            else:
                parts.append(self.scripted(size))
        return self.hcat(parts)

    def scripted(self, size):
        base = self.primary(size)
        while self.peek() in ('bar', 'under'):         # postfix: x bar
            base = self.overline(base, size, self.next() == 'under')
        kw = {}
        while self.peek() in ('sub', 'sup', 'from', 'to') and self.peek() not in kw:
            k = self.next()
            small = max(size * 0.7, 5.0)
            kw[k] = self.scripted(small) if k in ('sup', 'to') else self.primary(small)
        return self.attach(base, kw, size) if kw else base

    def primary(self, size):
        t = self.next()
        if t is None or t == '}':
            return self.empty()
        if isinstance(t, tuple):
            return self.text(t[1], 'R', size)
        if t == '{':
            b = self.seq(size, ('}',))
            self.next()
            return b
        if t in ('~', '^'):
            return self.space(size, t == '~')
        if t == 'sqrt':
            return self.radical(self.primary(size), size)
        if t in ('roman', 'italic', 'bold'):
            return self.refont(self.primary(size), {'roman': 'R', 'italic': 'I', 'bold': 'B'}[t])
        if t == 'size':
            n = self.next()
            try:
                return self.primary(float(n))
            except (TypeError, ValueError):
                return self.primary(size)
        if t in BIGOPS:
            return self.bigop(t, size)
        if t == 'left':
            ld = self.next()
            inner = self.seq(size, ('right',))
            rd = None
            if self.next() == 'right':
                rd = self.next()
            parts = [self.delimiter(ld, inner, size), inner]
            if rd is not None:
                parts.append(self.delimiter(rd, inner, size))
            return self.hcat(parts)
        return word(t, size, self)

    def delimiter(self, tok, inner, size):
        ch = tok[1] if isinstance(tok, tuple) else tok or ''
        if not ch:
            return Box()
        S = max(size, (inner.h + inner.d) * 1.1)
        y = (inner.h - inner.d) / 2 - 0.25 * S
        b = text(ch, 'R', S)
        return Box(b.w, y + 0.75 * S, 0.25 * S - y, shifted(b.items, 0, y))

    def fraction(self, num, den, size):
        axis, gap, pad = 0.25 * size, 0.15 * size, 0.1 * size
        w = max(num.w, den.w) + 2 * pad
        yn, yd = axis + gap + num.d, axis - gap - den.h
        items = (shifted(num.items, (w - num.w) / 2, yn) + shifted(den.items, (w - den.w) / 2, yd)
                 + [('r', 0.0, axis, w, size)])
        return Box(w, yn + num.h, -(yd - den.d), items)

    def radical(self, a, size):
        top = a.h + 0.1 * size
        S = max(size, (top + a.d) / 0.9)
        y = -a.d + 0.1 * S
        sign = text('√', 'R', S)
        items = shifted(sign.items, 0, y) + [('r', sign.w, top, a.w + 0.05 * size, size)] + shifted(a.items, sign.w)
        return Box(sign.w + a.w + 0.05 * size, top + 0.06 * size, max(a.d, 0.1 * S - y), items)

    def attach(self, base, kw, size):
        b = base
        if 'from' in kw or 'to' in kw:
            lo, hi, gap = kw.get('from', Box()), kw.get('to', Box()), 0.12 * size
            w = max(b.w, lo.w, hi.w)
            yl, yh = -(b.d + gap + lo.h), b.h + gap + hi.d
            items = (shifted(b.items, (w - b.w) / 2) + shifted(lo.items, (w - lo.w) / 2, yl)
                     + shifted(hi.items, (w - hi.w) / 2, yh))
            b = Box(w, max(b.h, yh + hi.h if hi.items else 0), max(b.d, -yl + lo.d if lo.items else 0), items)
        sup, sub = kw.get('sup'), kw.get('sub')
        if not sup and not sub:
            return b
        items, w = list(b.items), b.w
        h, d, extra = b.h, b.d, 0.0
        if sup:
            ys = max(0.42 * size, b.h - 0.55 * sup.h)
            items += shifted(sup.items, b.w + 0.05 * size, ys)
            h, extra = max(h, ys + sup.h), max(extra, sup.w + 0.05 * size)
        if sub:
            yb = -max(0.22 * size, b.d * 0.8)
            items += shifted(sub.items, b.w, yb)
            d, extra = max(d, -yb + sub.d), max(extra, sub.w)
        return Box(w + extra + 0.04 * size, h, d, items)


class Grid:
    """A block of text lines for neqn; base is the row of the baseline."""

    def __init__(self, lines=None, base=0):
        lines = lines or ['']
        self.w = max(map(len, lines))
        self.lines, self.base = [line.ljust(self.w) for line in lines], base

    @property
    def down(self):
        return len(self.lines) - 1 - self.base


def paint(parts):
    """Grids at (dx, dy): dy is the row of each part's baseline relative to the result's (up is minus)."""
    parts = [p for p in parts if p[0].w]
    if not parts:
        return Grid()
    top = min(dy - g.base for g, dx, dy in parts)
    bottom = max(dy + g.down for g, dx, dy in parts)
    rows = [[' '] * max(dx + g.w for g, dx, dy in parts) for _ in range(bottom - top + 1)]
    for g, dx, dy in parts:
        for r, line in enumerate(g.lines):
            for c, ch in enumerate(line):
                if ch != ' ':
                    rows[dy - g.base + r - top][dx + c] = ch
    return Grid([''.join(r) for r in rows], -top)


class AsciiEqn(Eqn):
    """neqn: equations for the terminal, superscripts on the line above, fractions over a row of -."""

    def text(self, t, font, size):
        return Grid([''.join(GREEK_NAMES.get(ch, ASCII.get(ch, ch)) for ch in t)])

    def hcat(self, boxes):
        parts, x = [], 0
        for g in boxes:
            parts.append((g, x, 0))
            x += g.w
        return paint(parts)

    def padded(self, box, pad):
        return self.hcat([Grid([' ']), box, Grid([' '])]) if pad else box

    def empty(self):
        return Grid()

    def space(self, size, wide):
        return Grid([' ']) if wide else Grid()

    def refont(self, b, f):
        return b

    def bigop(self, name, size):          # drawn in characters, three lines high
        return Grid({'sum': ['\\--', ' > ', '/--'], 'prod': ['____', '|  |', '|  |'],
                     'int': [' /', ' |', '/ '], 'union': ['   ', '| |', '\\_/'],
                     'inter': ['/-\\', '| |', '   ']}[name], 1)

    def overline(self, b, size, under):
        bar = Grid(['_' * b.w])
        return paint([(b, 0, 0), (bar, 0, b.down + 1 if under else -b.base - 1)])

    def fraction(self, num, den, size):
        w = max(num.w, den.w) + 2
        return paint([(num, (w - num.w) // 2, -1 - num.down), (Grid(['-' * w]), 0, 0),
                      (den, (w - den.w) // 2, 1 + den.base)])

    def radical(self, a, size):
        return paint([(a, 2, 0), (Grid(['_' * a.w]), 2, -a.base - 1), (Grid(['\\/']), 0, a.down)])

    def delimiter(self, tok, inner, size):
        ch = tok[1] if isinstance(tok, tuple) else tok or ''
        h = len(inner.lines)
        if not ch:
            return Grid()
        if h == 1:
            return Grid([ch])
        ends = {'(': ('/', '\\'), ')': ('\\', '/'), '[': ('[', '['), ']': (']', ']')}.get(ch, (ch, ch))
        mid = '|' if ch in '()' else ch
        return Grid([ends[0]] + [mid] * (h - 2) + [ends[1]], inner.base)

    def attach(self, base, kw, size):
        b = base
        if 'from' in kw or 'to' in kw:
            lo, hi = kw.get('from', Grid()), kw.get('to', Grid())
            w = max(b.w, lo.w, hi.w)
            b = paint([(b, (w - b.w) // 2, 0), (hi, (w - hi.w) // 2, -b.base - 1 - hi.down),
                       (lo, (w - lo.w) // 2, b.down + 1 + lo.base)])
        parts = [(b, 0, 0)]
        if kw.get('sup'):
            parts.append((kw['sup'], b.w, -b.base - 1 - kw['sup'].down))     # on the line above
        if kw.get('sub'):
            parts.append((kw['sub'], b.w, b.down + 1 + kw['sub'].base))
        return paint(parts)


def neqn(src, width=65):
    """eqn for nroff: each .EQ/.EN display becomes lines of characters, centred in no-fill mode."""
    out, eq = [], None
    for line in src.split('\n'):
        if eq is not None:
            if line.startswith('.EN'):
                g = AsciiEqn(' '.join(eq)).seq(10)
                pad = ' ' * max(0, (width - g.w) // 2)
                out += ['.sp', '.nf'] + ['\\&' + (pad + row).rstrip().replace('\\', '\\e') for row in g.lines]
                out += ['.fi', '.sp']
                eq = None
            else:
                eq.append(line)
            continue
        if line.startswith('.EQ'):
            eq = []
            continue
        out.append(line)
    if eq is not None:
        raise ValueError('EOF inside .EQ')
    return '\n'.join(out)


def layout(src, size=10.0):
    """One displayed equation -> one line of troff (no blanks, so troff keeps it whole)."""
    box = Eqn(src).seq(size)
    parts, cx, cy = [], 0.0, 0.0
    for it in box.items:
        k, x, y = it[:3]
        if abs(x - cx) > 1e-3:
            parts.append(f"\\h'{x - cx:.2f}p'")
            cx = x
        if abs(y - cy) > 1e-3:
            parts.append(f"\\v'{cy - y:.2f}p'")      # troff moves down for positive \v
            cy = y
        if k == 't':
            _, _, _, tt, font, sz, w = it
            parts.append(f"\\s'{sz:.1f}'\\f{font}{tt}")
            cx += w
        else:
            parts.append(f"\\l'{it[3]:.2f}p'")
            cx += it[3]
    parts.append(f"\\h'{box.w - cx:.2f}p'" + (f"\\v'{cy:.2f}p'" if abs(cy) > 1e-3 else '') + '\\s0\\fR')
    return ''.join(parts)


def eqn(src):
    """Replace each .EQ/.EN display with centred troff; everything else passes through."""
    out, size, eq = [], 10.0, None
    for line in src.split('\n'):
        if eq is not None:
            if line.startswith('.EN'):
                out += ['.sp 0.5', '.ce', layout(' '.join(eq), size), '.sp 0.5']
                eq = None
            else:
                eq.append(line)
            continue
        if line.startswith('.EQ'):
            eq = []
            continue
        m = re.match(r'\.ps\s+(\d+(?:\.\d+)?)', line)
        if m:
            size = float(m.group(1))
        out.append(line)
    if eq is not None:
        raise ValueError('EOF inside .EQ')
    return '\n'.join(out)

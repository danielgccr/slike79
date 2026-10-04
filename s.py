"""S as described in Becker & Chambers' 1981 Bell Labs manual (sections 2 "Basic Use" and 5 "Reference").

Vectors of mode logical/integer/real/character, matrices (column-major with a Dim),
the manual's grammar including `_` assignment and top-level command form (`q`, `list`),
three databases (working, save, shared), and graphics on a printer or a Tektronix 4014.
"""
import bisect
import math
import operator
import random
import re
import statistics
import time

import sdata
import sgraph
from vt import EOF, Interrupt

MAXLEN = 100_000        # ponytail: one VAX's worth of memory per session; stops 1:1e9 from eating the server
INT_MAX = 2 ** 31 - 1
BUDGET = 500_000        # values kept in a visitor's working and save directories: 25 visitors fit in 0.5 GB
TIME_LIMIT = 30         # seconds one top-level expression may run on this public machine


def size(v):
    return sum(size(c) for c in v.v) if v.mode == 'structure' else len(v)


class SError(Exception):
    def __init__(self, msg, where=None):
        super().__init__(msg)
        self.where = where


class SSyntax(Exception):
    def __init__(self, pos):
        self.pos = pos


class Incomplete(Exception):
    pass


class Quit(Exception):
    pass


class Break(Exception):
    pass


class Next(Exception):
    pass


# ---------------------------------------------------------------- data

MODES = ('logical', 'integer', 'real', 'character')
RANK = {m: i for i, m in enumerate(MODES)}


class Vec:
    __slots__ = ('mode', 'v', 'dim', 'names')

    def __init__(self, mode, v, dim=None, names=None):
        self.mode, self.v, self.dim, self.names = mode, list(v), dim, names
        if len(self.v) > MAXLEN:
            raise SError('vector too long')

    def __len__(self):
        return len(self.v)


def Lg(v, dim=None):
    return Vec('logical', v, dim)


def In(v, dim=None):
    return Vec('integer', v, dim)


def Re(v, dim=None):
    return Vec('real', [None if x is None else float(x) for x in v], dim)


def Ch(v, dim=None):
    return Vec('character', v, dim)


def to_str(x, mode):
    if mode == 'logical':
        return 'T' if x else 'F'
    if mode == 'real':
        return label_num(x)
    return str(x)


def label_num(x):
    return 'Inf' if x == math.inf else '-Inf' if x == -math.inf else 'NaN' if x != x else f'{x:.15g}'


def St(**components):
    """A hierarchical structure: named components, e.g. the x-y structure lowess returns."""
    return Vec('structure', components.values(), names=list(components))


def components(x):
    """(names, values) of a structure; a matrix is the structure Dim, Data (manual 3.2.1)."""
    if x.mode == 'structure':
        return x.names, x.v
    if x.dim:
        return ['Dim', 'Data'], [In(x.dim), Vec(x.mode, x.v)]
    raise SError('not a structure: $ selects components of structures')


def component(x, name):
    names, values = components(x)
    hits = [k for k, n in enumerate(names) if n == name] or [k for k, n in enumerate(names) if n.startswith(name)]
    if len(hits) != 1:
        raise SError(f'component "{name}" ' + ('is ambiguous' if hits else 'not found'))
    return values[hits[0]]


def no_structure(x):
    if x.mode == 'structure':
        raise SError('a structure is not data: select a component with $, as in z$y')


def coerce(x, mode):
    no_structure(x)
    if x.mode == mode:
        return x
    if mode == 'character':
        return Ch([None if v is None else to_str(v, x.mode) for v in x.v], x.dim)
    if x.mode == 'character':
        out = []
        for s in x.v:
            try:
                out.append(float(s))
            except (TypeError, ValueError):
                out.append(None)
        x = Re(out, x.dim)
        if mode == 'real':
            return x
    cast = {'logical': bool, 'integer': int, 'real': float}[mode]
    return Vec(mode, [None if v is None else cast(v) for v in x.v], x.dim)


def num(x):
    no_structure(x)
    if x.mode == 'character':
        raise SError('attempt to use character data in arithmetic')
    return [int(v) if isinstance(v, bool) else v for v in x.v]


def nona(vals):
    if None in vals:
        raise SError('missing values (NA) not allowed')
    return vals


def one(x, what='argument'):
    if x is None or not len(x) or x.v[0] is None:
        raise SError(f'{what} must be a single value')
    return num(x)[0] if x.mode != 'character' else x.v[0]


def truth(x):
    if not len(x):
        raise SError('empty condition')
    v = coerce(x, 'logical').v[0] if x.mode != 'character' else None
    if v is None:
        raise SError('missing value in condition')
    return v


def flat(vals):
    vals = [v for v in vals if v is not None]
    mode = max((v.mode for v in vals), key=RANK.get, default='logical')
    out = []
    for v in vals:
        out += coerce(v, mode).v
    return Vec(mode, out)


def dims(x):
    return x.dim or (len(x), 1)


# ---------------------------------------------------------------- printing

def fmt(x):
    """Format all elements with a common layout, as S prints vectors."""
    m = x.mode
    if m == 'character':
        return ['NA' if s is None else '"' + s + '"' for s in x.v]
    if m == 'logical':
        return ['NA' if v is None else 'T' if v else 'F' for v in x.v]
    if m == 'integer':
        return ['NA' if v is None else str(v) for v in x.v]
    return fmt_reals(x.v)


def decimals(v, sig=7):
    if v == 0:
        return 0
    d = max(0, sig - 1 - math.floor(math.log10(abs(v))))
    s = f'{v:.{d}f}'.rstrip('0')
    return len(s.split('.')[1]) if '.' in s else 0


def mantissa_digits(v):
    m = f'{v:.6e}'.split('e')[0].rstrip('0')
    return len(m) - m.index('.') - 1


def fmt_reals(vs):
    fin = [v for v in vs if v is not None and math.isfinite(v)]
    d = max((decimals(v) for v in fin), default=0)
    big = max((abs(v) for v in fin), default=0)
    if d > 9 or big >= 1e15:
        k = max((mantissa_digits(v) for v in fin), default=0)
        f = lambda v: f'{v:.{k}e}'
    else:
        f = lambda v: f'{v:.{d}f}'
    return ['NA' if v is None else f(v) if math.isfinite(v) else label_num(v) for v in vs]


def show_vector(x, W=80):
    items = fmt(x)
    if not items:
        return ['NULL']
    w = max(map(len, items))
    n = len(items)
    if 1 + n * (w + 1) <= W:
        return [''.join(' ' + s.rjust(w) for s in items)]
    dig = len(str(n))
    lab = dig + 2
    per = max(1, (W - lab) // (w + 1))
    return [(' ' * lab if k == 0 else f'[{k + 1:>{dig}}]') + ''.join(' ' + s.rjust(w) for s in items[k:k + per])
            for k in range(0, n, per)]


def show_matrix(x, rowlab=None, collab=None, W=80):
    nr, nc = x.dim
    cols = [fmt(Vec(x.mode, x.v[j * nr:(j + 1) * nr])) for j in range(nc)]
    heads = [collab[j] if collab and j < len(collab) else f'[,{j + 1}]' for j in range(nc)]
    rl = [rowlab[i] if rowlab and i < len(rowlab) else f'[{i + 1:>{len(str(nr))}},]' for i in range(nr)]
    rw = max(map(len, rl), default=0)
    widths = [max([len(heads[j])] + [len(s) for s in cols[j]]) + 2 for j in range(nc)]
    lines = ['Array:', f'{nr} by {nc}']
    j0 = 0
    while j0 < nc:
        j1, used = j0, rw
        while j1 < nc and (j1 == j0 or used + widths[j1] <= W):
            used += widths[j1]
            j1 += 1
        lines.append(' ' * rw + ''.join(heads[j].rjust(widths[j]) for j in range(j0, j1)))
        for i in range(nr):
            lines.append(rl[i].ljust(rw) + ''.join(cols[j][i].rjust(widths[j]) for j in range(j0, j1)))
        j0 = j1
    return lines


def show(x, rowlab=None, collab=None):
    if x.mode == 'structure':     # layout ours: the 1981 manual names components but shows no printout
        return ''.join(f'{n}:\n' + show(c) for n, c in zip(x.names, x.v))
    return '\n'.join(show_matrix(x, rowlab, collab) if x.dim else show_vector(x)) + '\n'


# ---------------------------------------------------------------- lexer

TOKEN = re.compile(r'''(?P<sp>[ \t\r]+|\#[^\n]*)|(?P<nl>\n)
 |(?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)
 |(?P<name>[A-Za-z][A-Za-z0-9.]*)
 |(?P<str>"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*')
 |(?P<op><-|->|\*\*|%.|<=|>=|==|!=|[-+*/^<>!&|:$_=(){}\[\],;])''', re.X)
RESERVED = {'if', 'else', 'repeat', 'while', 'for', 'in', 'next', 'break'}
CONSTS = {'T': [True], 'TRUE': [True], 'F': [False], 'FALSE': [False], 'NA': [None]}


def ends_expr(t):
    k, s, _ = t
    return k in ('num', 'str', 'name') or (k == 'kw' and s in ('break', 'next')) or (k == 'op' and s in ')]}')


def lex(src):
    toks, depth, i = [], [], 0
    while i < len(src):
        m = TOKEN.match(src, i)
        if not m:
            raise SSyntax(i)
        kind, text, i = m.lastgroup, m.group(), m.end()
        if kind == 'sp':
            continue
        if kind == 'nl':
            # a newline ends a statement only where the expression could end (manual 5.1.3)
            if (depth and depth[-1] in '([') or not toks or not ends_expr(toks[-1]):
                continue
        elif kind == 'name' and text in RESERVED:
            kind = 'kw'
        elif kind == 'op':
            if text in '([{':
                depth.append(text)
            elif text in ')]}' and depth:
                depth.pop()
        toks.append((kind, text, m.start()))
    toks.append(('eof', '', len(src)))
    return toks


def unquote(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t'}.get(m.group(1), m.group(1)), s[1:-1])


# ---------------------------------------------------------------- parser

BINARY = {'<-': 1, '_': 1, '->': 2, '|': 3, '&': 4, '==': 6, '!=': 6, '<': 6, '>': 6, '<=': 6, '>=': 6,
          '+': 7, '-': 7, '*': 8, '/': 8, ':': 10, '^': 12, '**': 12, '(': 13, '[': 13, '$': 13}


def is_op(t, s):
    return t[0] == 'op' and t[1] == s


def is_sep(t):
    return t[0] == 'nl' or is_op(t, ';')


class Parser:
    def __init__(self, src):
        self.t, self.i, self.braces = lex(src), 0, 0

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def next(self):
        t = self.peek()
        self.i += 1
        return t

    def fail(self, t):
        raise Incomplete if t[0] == 'eof' else SSyntax(t[2])

    def expect(self, s):
        t = self.next()
        if t[1] != s or t[0] not in ('op', 'kw'):
            self.fail(t)

    def skipnl(self):
        while self.peek()[0] == 'nl':
            self.i += 1

    def program(self):
        out = []
        while True:
            while is_sep(self.peek()):
                self.i += 1
            if self.peek()[0] == 'eof':
                return out
            t, n = self.peek(), self.peek(1)
            if t[0] == 'name' and n[0] in ('name', 'num', 'str') and n[2] > t[2] + len(t[1]):
                self.i += 1               # command form: plot x,y is plot(x,y) (1981 manual, "syntax")
                out.append(('call', t[1], self.command_args()))
            else:
                out.append(self.expr())
            t = self.peek()
            if not (is_sep(t) or t[0] == 'eof'):
                self.fail(t)

    def command_args(self):
        args = []
        while True:
            t = self.peek()
            if t[0] in ('name', 'str') and is_op(self.peek(1), '='):
                self.i += 2
                args.append((t[1] if t[0] == 'name' else unquote(t[1]), self.expr()))
            else:
                args.append((None, self.expr()))
            if not is_op(self.peek(), ','):
                return args
            self.i += 1

    def bp(self, t):
        if t[0] != 'op':
            return 0
        return 9 if t[1].startswith('%') else BINARY.get(t[1], 0)

    def expr(self, rbp=0):
        left = self.nud(self.next())
        while True:
            t = self.peek()
            b = self.bp(t)
            if b <= rbp:
                return left
            self.i += 1
            left = self.led(t, left, b)

    def target(self, node, t):
        if not (node[0] == 'name' or (node[0] == 'index' and node[1][0] == 'name')):
            raise SSyntax(t[2])

    def led(self, t, left, b):
        s = t[1]
        if s == '(':
            if left[0] != 'name':
                raise SSyntax(t[2])
            return ('call', left[1], self.args(')'))
        if s == '[':
            return ('index', left, self.args(']'))
        if s == '$':
            n = self.next()
            if is_op(n, '['):
                e = self.expr()
                self.expect(']')
                return ('dollar_n', left, e)
            if n[0] != 'name':
                self.fail(n)
            return ('dollar', left, n[1])
        if s in ('<-', '_'):
            self.target(left, t)
            return ('assign', left, self.expr(b - 1))
        if s == '->':
            right = self.expr(b)
            self.target(right, t)
            return ('assign', right, left)
        right = self.expr(b - 1 if s in ('^', '**') else b)
        return ('call', s, [(None, left), (None, right)])

    def args(self, close):
        out = []
        while True:
            t = self.peek()
            if t[0] == 'op' and t[1] in (',', close):
                out.append((None, None))
            elif t[0] in ('name', 'str') and is_op(self.peek(1), '='):
                self.i += 2
                n = self.peek()
                val = None if n[0] == 'op' and n[1] in (',', close) else self.expr()
                out.append((t[1] if t[0] == 'name' else unquote(t[1]), val))
            else:
                out.append((None, self.expr()))
            t = self.next()
            if is_op(t, close):
                return [] if out == [(None, None)] else out
            if not is_op(t, ','):
                self.fail(t)

    def body(self):
        self.skipnl()
        return self.expr()

    def nud(self, t):
        k, s, _ = t
        if k == 'num':
            return ('const', In([int(s)]) if s.isdigit() else Re([float(s)]))
        if k == 'str':
            return ('const', Ch([unquote(s)]))
        if k == 'name':
            if s in CONSTS and not is_op(self.peek(), '('):
                return ('const', Lg(CONSTS[s]))
            return ('name', s)
        if k == 'op':
            if s == '(':
                e = self.expr()
                self.expect(')')
                return ('paren', e)
            if s == '{':
                self.braces += 1
                stmts = []
                while True:
                    while is_sep(self.peek()):
                        self.i += 1
                    if is_op(self.peek(), '}'):
                        self.i += 1
                        self.braces -= 1
                        return ('block', stmts)
                    stmts.append(self.expr())
                    n = self.peek()
                    if not (is_sep(n) or is_op(n, '}')):
                        self.fail(n)
            if s == '$':
                n = self.next()
                if n[0] == 'name' and n[2] == t[2] + 1:
                    return ('name', n[1])
                self.fail(n)
            if s in ('-', '+'):
                return ('call', s, [(None, self.expr(11))])
            if s == '!':
                return ('call', '!', [(None, self.expr(5))])
        if k == 'kw':
            if s == 'if':
                self.expect('(')
                cond = self.expr()
                self.expect(')')
                yes = self.body()
                j = self.i
                if self.braces:             # inside { } an else may start the next line
                    self.skipnl()
                if self.peek()[:2] == ('kw', 'else'):
                    self.i += 1
                    return ('if', cond, yes, self.body())
                self.i = j
                return ('if', cond, yes, None)
            if s == 'for':
                self.expect('(')
                var = self.next()
                if var[0] != 'name':
                    self.fail(var)
                self.expect('in')
                seq = self.expr()
                self.expect(')')
                return ('for', var[1], seq, self.body())
            if s == 'while':
                self.expect('(')
                cond = self.expr()
                self.expect(')')
                return ('while', cond, self.body())
            if s == 'repeat':
                return ('repeat', self.body())
            if s in ('break', 'next'):
                return (s,)
        self.fail(t)


def parse(src):
    return Parser(src).program()


# ---------------------------------------------------------------- operators

def div(p, q):
    try:
        return p / q
    except ZeroDivisionError:
        return math.nan if p == 0 else math.copysign(math.inf, p)


def power(p, q):
    try:
        return math.pow(p, q)
    except ValueError:
        return math.nan
    except OverflowError:
        return math.inf


ARITH = {'+': operator.add, '-': operator.sub, '*': operator.mul, '/': div, '^': power, '**': power,
         '%/': lambda p, q: None if q == 0 else p // q,
         '%%': lambda p, q: None if q == 0 else p % q}
COMPARE = {'==': operator.eq, '!=': operator.ne, '<': operator.lt, '>': operator.gt,
           '<=': operator.le, '>=': operator.ge}


def dim_of(a, b, n):
    return a.dim if a.dim and len(a) == n else b.dim if b.dim and len(b) == n else None


def arith(op, a, b=None):
    if b is None:
        x = num(a)
        mode = 'integer' if a.mode in ('logical', 'integer') else 'real'
        return Vec(mode, [None if v is None else (-v if op == '-' else v) for v in x], a.dim)
    x, y = num(a), num(b)
    n = max(len(x), len(y)) if x and y else 0
    ints = a.mode in ('logical', 'integer') and b.mode in ('logical', 'integer')
    mode = 'integer' if ints and op in ('+', '-', '*', '%/', '%%') else 'real'
    f = ARITH[op]
    out = []
    for i in range(n):
        p, q = x[i % len(x)], y[i % len(y)]
        r = None if p is None or q is None else f(p, q)
        if r is not None and mode == 'integer' and abs(r) > INT_MAX:
            r = None                                  # 32-bit integer overflow -> NA
        out.append(r)
    return (In if mode == 'integer' else Re)(out, dim_of(a, b, n))


def compare(op, a, b):
    if 'character' in (a.mode, b.mode):
        x, y = coerce(a, 'character').v, coerce(b, 'character').v
    else:
        x, y = num(a), num(b)
    n = max(len(x), len(y)) if x and y else 0
    f = COMPARE[op]
    out = [None if x[i % len(x)] is None or y[i % len(y)] is None else f(x[i % len(x)], y[i % len(y)])
           for i in range(n)]
    return Lg(out, dim_of(a, b, n))


def logic(op, a, b=None):
    x = coerce(a, 'logical').v if a.mode != 'character' else num(a)
    if b is None:
        return Lg([None if v is None else not v for v in x], a.dim)
    y = coerce(b, 'logical').v if b.mode != 'character' else num(b)
    n = max(len(x), len(y)) if x and y else 0
    out = []
    for i in range(n):
        p, q = x[i % len(x)], y[i % len(y)]
        if op == '&':
            out.append(False if p is False or q is False else None if p is None or q is None else True)
        else:
            out.append(True if p is True or q is True else None if p is None or q is None else False)
    return Lg(out, dim_of(a, b, n))


def colon(a, b):
    p, q = one(a, 'from'), one(b, 'to')
    step = 1 if q >= p else -1
    n = int(math.floor(abs(q - p) + 1e-10)) + 1
    if n > MAXLEN:
        raise SError('vector too long')
    if p == int(p):
        return In([int(p) + step * k for k in range(n)])
    return Re([p + step * k for k in range(n)])


def op_call(op, vals):
    for v in vals:
        no_structure(v)
    if op in ARITH:
        if len(vals) == 1 and op not in ('-', '+'):
            raise SError('missing operand')
        return arith(op, *vals)
    if op in COMPARE:
        return compare(op, *vals)
    if op in ('&', '|', '!'):
        return logic(op, *vals)
    if op == ':':
        return colon(*vals)
    raise SError(f'operator "{op}" not defined')


OPERATORS = set(ARITH) | set(COMPARE) | {'&', '|', '!', ':'}


# ---------------------------------------------------------------- subscripts

def positions(i, n):
    """0-based positions selected by subscript i of a length-n vector; None marks NA."""
    if i is None:
        return list(range(n))
    if i.mode == 'logical':
        if not len(i):
            return []
        out = []
        for k in range(max(n, len(i))):
            v = i.v[k % len(i)]
            if v is None:
                out.append(None)
            elif v:
                out.append(k)
        return out
    if i.mode == 'character':
        raise SError('character subscripts are not supported')
    v = [None if x is None else int(x) for x in num(i)]
    if any(x is not None and x < 0 for x in v):
        if any(x is None or x > 0 for x in v):
            raise SError("can't mix positive and negative subscripts")
        drop = {-x - 1 for x in v}
        return [k for k in range(n) if k not in drop]
    return [None if x is None else x - 1 for x in v if x != 0]


def get_index(x, idx):
    no_structure(x)
    if len(idx) <= 1:
        pos = positions(idx[0] if idx else None, len(x))
        return Vec(x.mode, [x.v[p] if p is not None and p < len(x) else None for p in pos])
    if not x.dim or len(idx) != 2:
        raise SError('wrong number of subscripts')
    nr, nc = x.dim
    ri, ci = positions(idx[0], nr), positions(idx[1], nc)
    if any(p is None or p >= nr for p in ri) or any(p is None or p >= nc for p in ci):
        raise SError('subscript out of range')
    vals = [x.v[r + c * nr] for c in ci for r in ri]
    return Vec(x.mode, vals, (len(ri), len(ci)) if len(ri) > 1 and len(ci) > 1 else None)


def set_index(x, idx, val):
    no_structure(x)
    mode = max(x.mode, val.mode, key=RANK.get)
    x, val = coerce(x, mode), coerce(val, mode)
    v = list(x.v)
    if len(idx) <= 1:
        pos = positions(idx[0] if idx else None, len(x))
        dim = x.dim
    else:
        if not x.dim or len(idx) != 2:
            raise SError('wrong number of subscripts')
        nr, nc = x.dim
        ri, ci = positions(idx[0], nr), positions(idx[1], nc)
        if any(p is None or p >= nr for p in ri) or any(p is None or p >= nc for p in ci):
            raise SError('subscript out of range')
        pos, dim = [r + c * nr for c in ci for r in ri], x.dim
    if None in pos:
        raise SError('NA subscript in assignment')
    if pos and not len(val):
        raise SError('replacement has length zero')
    for k, p in enumerate(pos):
        if p >= len(v):
            v.extend([None] * (p + 1 - len(v)))
        v[p] = val.v[k % len(val)]
    return Vec(mode, v, dim if len(v) == len(x) else None)


# ---------------------------------------------------------------- builtins

BUILTINS = {}


class Builtin:
    def __init__(self, f, formals, doc, quote, structs):
        self.f, self.formals, self.doc, self.quote, self.structs = f, formals, doc, quote, structs

    def usage(self, name):
        return f'{name}({", ".join(self.formals)})'


class A(dict):
    __getattr__ = dict.get

    def __missing__(self, key):
        return None


def fn(name, formals='', doc='', quote=False, structs=False):
    """Register a builtin. Formals: `x` required, `x=` optional, `...` any number."""
    def deco(f):
        BUILTINS[name] = Builtin(f, formals.split(), doc, quote, structs)
        return f
    return deco


def shared_db():
    x77 = Re(sdata.STATE_X77, (50, 8))
    return {
        'Weekdays': Ch(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']),
        'Month.length': In([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]),
        'month.abb': Ch(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']),
        'state.abb': Ch(sdata.STATE_ABB),
        'state.name': Ch(sdata.STATE_NAME),
        'state.x77': x77,
        'state.vars': Ch(sdata.STATE_X77_COLS),
        'votes.repub': Re(sdata.VOTES_REPUB, (50, len(sdata.VOTES_YEAR))),
        'votes.year': In(sdata.VOTES_YEAR),
        **smacro.system_macros(),                 # the macros of manual section 4.8
    }


class Interp:
    def __init__(self, io, shell=None):
        self.io, self.shell = io, shell
        self.db = [{}, {}, shared_db()]
        self.local = {}
        self.rng = random.Random()
        self.dev, self.frame, self.pending, self.pch = 'printer', None, False, '*'
        self.prompts = True          # off when S reads its commands from a file: S < analysis
        self.deadline = None

    def write(self, s):
        self.io.write(s)

    # -- session
    def repl(self):
        while True:
            try:
                if self.prompts:
                    self.write('> ')
                src = self.io.readline()
                if src.startswith('!'):
                    if self.shell:
                        self.shell.run_line(src[1:])
                    continue
                text = src
                while True:
                    try:
                        text = smacro.expand(self, src) if '?' in src else src
                        stmts = parse(text)
                        break
                    except Incomplete:
                        if self.prompts:
                            self.write('+ ')
                        src += '\n' + self.io.readline()
            except Interrupt:
                continue
            except EOF:
                return
            except SSyntax as e:                 # shown in the expanded text, where the error is
                start = text.rfind('\n', 0, e.pos) + 1
                end = text.find('\n', e.pos)
                self.write('Syntax error\n' + text[start:end if end >= 0 else None] + '\n'
                           + ' ' * (e.pos - start) + '^\n')
                continue
            except SError as e:                  # from the macro processor: FATAL, undefined macro
                self.write(f'Error: {e}\n')
                continue
            try:
                for node in stmts:
                    self.deadline = time.monotonic() + TIME_LIMIT
                    self.top(node)
            except SError as e:
                self.write(f'Error: {e}\n' + (f'Error in {e.where}\n' if e.where else ''))
            except Interrupt:
                pass
            except Quit:
                return
            except RecursionError:
                self.write('Error: expression too deeply nested\n')

    def top(self, node):
        if node[0] == 'name' and node[1] in BUILTINS:
            # 1981 manual: a line of only a name is first a function call with no arguments;
            # only if there is no such function is it a dataset to print. (q, list, printer)
            v = self.call(node[1], [])
        else:
            v = self.ev(node)
        if v is not None and node[0] not in ('assign', 'for', 'while'):
            self.write(show(v))

    def run(self, src):
        """Evaluate source text non-interactively (used by tests and help examples)."""
        for node in parse(smacro.expand(self, src) if '?' in src else src):
            self.deadline = time.monotonic() + TIME_LIMIT
            self.top(node)

    # -- databases
    def has(self, n):
        return n in self.local or any(n in d for d in self.db)

    def lookup(self, n):
        if n in self.local:
            return self.local[n]
        for d in self.db:
            if n in d:
                return d[n]
        if n in BUILTINS:
            raise SError(f'function "{n}" used as data')
        raise SError(f'dataset "{n}" not found')   # wording ours: the manual shows only the Error: form

    def store(self, n, v):
        if n in self.local:
            self.local[n] = v
        else:
            self.put(0, n, v)

    def put(self, pos, name, value):
        """Store on the working (0) or save (1) directory, within the visitor's budget."""
        db = self.db[pos]
        used = sum(size(v) for d in self.db[:2] for v in d.values()) - (size(db[name]) if name in db else 0)
        if pos < 2 and used + size(value) > BUDGET:
            raise SError(f'datasets would hold over {BUDGET:,} values, the limit here: rm some first')
        db[name] = value

    def check(self):
        """Called in long loops: ^C, a hang-up, or the time limit stops the expression."""
        self.io.check()
        if self.deadline and time.monotonic() > self.deadline:
            self.deadline = None
            raise SError(f'stopped after {TIME_LIMIT} seconds, the limit for one expression here')

    # -- evaluation
    def ev(self, n):
        k = n[0]
        if k == 'const':
            return n[1]
        if k == 'name':
            return self.lookup(n[1])
        if k == 'paren':
            return self.ev(n[1])
        if k == 'call':
            return self.call(n[1], n[2])
        if k == 'index':
            return get_index(self.ev(n[1]), [None if e is None else self.ev(e) for _, e in n[2]])
        if k == 'assign':
            tgt, val = n[1], self.ev(n[2])
            if val is None:
                raise SError('nothing to assign')
            if tgt[0] == 'name':
                self.store(tgt[1], val)
            else:
                name = tgt[1][1]
                idx = [None if e is None else self.ev(e) for _, e in tgt[2]]
                self.store(name, set_index(self.lookup(name), idx, val))
            return val
        if k == 'dollar':
            return component(self.ev(n[1]), n[2])
        if k == 'dollar_n':
            names, values = components(self.ev(n[1]))
            i = int(one(self.ev(n[2]), 'component number'))
            if not 1 <= i <= len(values):
                raise SError(f'component {i} not found: there are {len(values)}')
            return values[i - 1]
        if k == 'if':
            if truth(self.ev(n[1])):
                return self.ev(n[2])
            return self.ev(n[3]) if n[3] else None
        if k == 'block':
            val = None
            for s in n[1]:
                v = self.ev(s)
                val = val if v is None else v
            return val
        if k == 'for':
            seq, var = self.ev(n[2]), n[1]
            saved = self.local.get(var)
            try:
                for x in seq.v:
                    self.check()
                    self.local[var] = Vec(seq.mode, [x])
                    try:
                        self.ev(n[3])
                    except Next:
                        continue
                    except Break:
                        break
            finally:
                if saved is None:
                    self.local.pop(var, None)
                else:
                    self.local[var] = saved
            return None
        if k in ('while', 'repeat'):
            val = None
            while k == 'repeat' or truth(self.ev(n[1])):
                self.check()
                try:
                    v = self.ev(n[-1])
                    val = val if v is None else v
                except Next:
                    continue
                except Break:
                    break
            return val if k == 'repeat' else None
        if k == 'break':
            raise Break
        if k == 'next':
            raise Next
        raise SError(f'cannot evaluate {k}')

    def call(self, name, args):
        try:
            if name in OPERATORS:
                return op_call(name, [self.ev(e) for _, e in args])
            b = BUILTINS.get(name)
            if not b:
                raise SError(f'function "{name}" not found')
            return b.f(self, self.match(name, b, args))
        except SError as e:
            e.where = e.where or name
            raise

    def match(self, fname, b, args):
        """Argument matching of manual 5.2.1: exact name, unique prefix, then position."""
        formals = [f.rstrip('=') for f in b.formals]
        named = [(n, e) for n, e in args if n is not None]
        positional = [e for n, e in args if n is None]
        bound = {}
        for n, e in list(named):
            if n in formals and n != '...' and n not in bound:
                bound[n] = e
                named.remove((n, e))
        for n, e in list(named):
            cands = [f for f in formals if f.startswith(n) and f not in bound and f != '...']
            if len(cands) > 1:
                raise SError(f'argument "{n}" matches several formals')
            if cands:
                bound[cands[0]] = e
                named.remove((n, e))
        dots = []
        before = formals[:formals.index('...')] if '...' in formals else formals
        for f in before:
            if f not in bound and positional:
                bound[f] = positional.pop(0)
        if '...' in formals:
            dots = [(None, e) for e in positional] + named
        elif positional or named:
            raise SError(f'unused argument "{named[0][0]}"' if named else 'too many arguments')
        a = A()
        a['_nodes'] = bound
        for spec, f in zip(b.formals, formals):
            if f != '...' and not spec.endswith('=') and bound.get(f) is None:
                raise SError(f'argument "{f}" is missing')
        if b.quote:
            a.update(bound)
            a['...'] = dots
            return a
        for f, e in bound.items():
            if e is not None:
                a[f] = self.ev(e)
        a['...'] = [self.ev(e) for _, e in dots if e is not None]
        if not b.structs:
            for v in [*(v for k, v in a.items() if isinstance(v, Vec)), *a['...']]:
                no_structure(v)
        return a

    # -- graphics devices
    def new_frame(self, fr):
        if self.dev == 'printer' and self.frame and self.pending:
            self.write(sgraph.printer(self.frame) + '\n')   # manual: always one frame behind
        self.frame, self.pending = fr, True
        self.refresh(erase=True)

    def refresh(self, erase=False):
        if self.dev == 'tek14':
            self.write(sgraph.osc(sgraph.svg(self.frame), erase))

    def need_frame(self):
        if not self.frame:
            raise SError('no current plot')
        return self.frame


# -- combining and sequences

@fn('c', '...', 'combine values into one vector')
def _c(I, a):
    return flat(a['...'])


@fn('seq', 'from to= by=', 'seq(n) is 1:n, seq(x) is 1:len(x), seq(from,to), seq(from,to,by)')
def _seq(I, a):
    f = a['from']
    if a.to is None and a.by is None:
        return colon(In([1]), f) if len(f) == 1 else In(range(1, len(f) + 1))
    if a.to is None:
        raise SError('argument "to" is missing')
    if a.by is None:
        return colon(f, a.to)
    p, q, s = one(f), one(a.to), one(a.by)
    if s == 0 or (q - p) * s < 0:
        raise SError('wrong sign in by')
    n = int(math.floor((q - p) / s + 1e-10)) + 1
    if n > MAXLEN:
        raise SError('vector too long')
    if all(isinstance(v, int) for v in (p, s)):
        return In([p + k * s for k in range(n)])
    return Re([round(p + k * s, 12) for k in range(n)])


@fn('rep', 'x times', 'repeat x; times may be one count or one count per element')
def _rep(I, a):
    x, t = a.x, [int(v) for v in nona(num(a.times))]
    if len(t) == 1:
        if len(x) * t[0] > MAXLEN:
            raise SError('vector too long')
        return Vec(x.mode, x.v * max(t[0], 0))
    if len(t) != len(x):
        raise SError('times must have length 1 or len(x)')
    out = []
    for v, k in zip(x.v, t):
        out += [v] * k
    return Vec(x.mode, out)


# -- attributes and missing values

@fn('len', 'x', 'number of elements')
def _len(I, a):
    return In([len(a.x)])


@fn('mode', 'x', 'mode of the data: logical, integer, real, character or structure', structs=True)
def _mode(I, a):
    return Ch([a.x.mode])


@fn('NA', 'x', 'TRUE where x is missing')
def _na(I, a):
    return Lg([v is None for v in a.x.v], a.x.dim)


# -- summaries

def numbers(vals):
    x = flat(vals)
    return x, nona(num(x))


@fn('sum', '...', 'sum of all the values')
def _sum(I, a):
    x, v = numbers(a['...'])
    return (In if x.mode in ('logical', 'integer') else Re)([sum(v)])


@fn('prod', '...', 'product of all the values')
def _prod(I, a):
    return Re([math.prod(numbers(a['...'])[1])])


def extreme(a, f):
    x = flat(a['...'])
    v = nona(x.v if x.mode == 'character' else num(x))
    if not v:
        raise SError('no data')
    return Vec('integer' if x.mode == 'logical' else x.mode, [f(v)])


@fn('max', '...', 'largest value')
def _max(I, a):
    return extreme(a, max)


@fn('min', '...', 'smallest value')
def _min(I, a):
    return extreme(a, min)


@fn('range', '...', 'c(min, max)')
def _range(I, a):
    return flat([extreme(a, min), extreme(a, max)])


@fn('mean', 'x trim=', 'mean; trim= drops that fraction from each end')
def _mean(I, a):
    v = sorted(nona(num(a.x)))
    if not v:
        raise SError('no data')
    trim = one(a.trim) if a.trim else 0
    if not 0 <= trim < 0.5:
        raise SError('trim must be in [0, .5)')
    k = int(len(v) * trim)
    return Re([statistics.fmean(v[k:len(v) - k])])


@fn('median', 'x', 'median')
def _median(I, a):
    v = nona(num(a.x))
    if not v:
        raise SError('no data')
    return Re([statistics.median(v)])


@fn('var', 'x', 'sample variance')
def _var(I, a):
    v = nona(num(a.x))
    if len(v) < 2:
        raise SError('need at least 2 values')
    return Re([statistics.variance(v)])


# -- sorting and matching

def sort_key(v):
    return (v is None, v if v is not None else 0)


@fn('sort', 'x', 'values in increasing order, NAs dropped')
def _sort(I, a):
    return Vec(a.x.mode, sorted(v for v in a.x.v if v is not None))


@fn('order', '...', 'permutation that sorts the first argument, ties broken by the next')
def _order(I, a):
    keys = a['...']
    if not keys:
        raise SError('no arguments')
    n = len(keys[0])
    if any(len(k) != n for k in keys):
        raise SError('arguments have different lengths')
    return In([i + 1 for i in sorted(range(n), key=lambda i: tuple(sort_key(k.v[i]) for k in keys))])


@fn('rank', 'x', 'ranks, ties averaged')
def _rank(I, a):
    v = nona(a.x.v if a.x.mode == 'character' else num(a.x))
    idx = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and v[idx[j + 1]] == v[idx[i]]:
            j += 1
        for k in range(i, j + 1):
            r[idx[k]] = (i + j) / 2 + 1
        i = j + 1
    return Re(r)


@fn('rev', 'x', 'elements in reverse order')
def _rev(I, a):
    return Vec(a.x.mode, a.x.v[::-1])


@fn('match', 'x table', 'position of each x in table, NA if absent')
def _match(I, a):
    mode = max(a.x.mode, a.table.mode, key=RANK.get)
    t = coerce(a.table, mode).v
    first = {}
    for i, v in enumerate(t):
        first.setdefault(v, i + 1)
    return In([first.get(v) for v in coerce(a.x, mode).v])


@fn('unique', 'x', 'values with duplicates removed')
def _unique(I, a):
    seen, out = set(), []
    for v in a.x.v:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return Vec(a.x.mode, out)


@fn('all', '...', 'TRUE if every value is TRUE')
def _all(I, a):
    v = coerce(flat(a['...']), 'logical').v
    return Lg([False if False in v else None if None in v else True])


@fn('any', '...', 'TRUE if some value is TRUE')
def _any(I, a):
    v = coerce(flat(a['...']), 'logical').v
    return Lg([True if True in v else None if None in v else False])


@fn('cumsum', 'x', 'cumulative sums')
def _cumsum(I, a):
    out, s = [], 0
    for v in num(a.x):
        s = None if s is None or v is None else s + v
        out.append(s)
    return (In if a.x.mode in ('logical', 'integer') else Re)(out)


@fn('diff', 'x lag=', 'x[i+lag] - x[i]')
def _diff(I, a):
    v, k = num(a.x), int(one(a.lag)) if a.lag else 1
    out = [None if p is None or q is None else q - p for p, q in zip(v, v[k:])]
    return (In if a.x.mode in ('logical', 'integer') else Re)(out)


# -- arithmetic functions

def math1(name, f, doc, keep_int=False):
    def g(I, a):
        x = a.x
        out = []
        for v in num(x):
            if v is None:
                out.append(None)
                continue
            try:
                out.append(f(v))
            except (ValueError, OverflowError):
                out.append(math.nan)
        if keep_int and x.mode in ('logical', 'integer'):
            return In(out, x.dim)
        return Re(out, x.dim)
    fn(name, 'x', doc)(g)


for _name, _f, _doc in [
        ('sqrt', math.sqrt, 'square root'), ('exp', math.exp, 'exponential'),
        ('log', lambda v: math.log(v) if v > 0 else -math.inf if v == 0 else math.nan, 'natural logarithm'),
        ('log10', lambda v: math.log10(v) if v > 0 else -math.inf if v == 0 else math.nan, 'base-10 logarithm'),
        ('sin', math.sin, 'sine (radians)'), ('cos', math.cos, 'cosine (radians)'),
        ('asin', math.asin, 'arc sine'), ('acos', math.acos, 'arc cosine'), ('atan', math.atan, 'arc tangent'),
        ('ceiling', math.ceil, 'smallest integer not below x'), ('floor', math.floor, 'largest integer not above x'),
        ('trunc', math.trunc, 'integer part, toward zero')]:
    math1(_name, _f, _doc)
math1('abs', abs, 'absolute value', keep_int=True)


@fn('round', 'x digits=', 'round to digits decimal places (default 0)')
def _round(I, a):
    d = int(one(a.digits)) if a.digits else 0
    return Re([None if v is None else round(v, d) for v in num(a.x)], a.x.dim)


# -- matrices

@fn('matrix', 'data nrow= ncol= byrow=', 'matrix filled by column (byrow=T: by row)')
def _matrix(I, a):
    d = a.data
    n = len(d)
    if not n:
        raise SError('no data')
    nr = int(one(a.nrow)) if a.nrow else None
    nc = int(one(a.ncol)) if a.ncol else None
    if nr is None and nc is None:
        nr, nc = n, 1
    elif nr is None:
        nr = math.ceil(n / nc)
    elif nc is None:
        nc = math.ceil(n / nr)
    if nr < 1 or nc < 1 or nr * nc > MAXLEN:
        raise SError('bad dimensions')
    vals = [d.v[k % n] for k in range(nr * nc)]
    if a.byrow and truth(a.byrow):
        vals = [vals[i * nc + j] for j in range(nc) for i in range(nr)]
    return Vec(d.mode, vals, (nr, nc))


@fn('nrow', 'x', 'number of rows')
def _nrow(I, a):
    return In([dims(a.x)[0]])


@fn('ncol', 'x', 'number of columns')
def _ncol(I, a):
    return In([dims(a.x)[1]])


def transpose(x):
    nr, nc = dims(x)
    return Vec(x.mode, [x.v[i + j * nr] for i in range(nr) for j in range(nc)], (nc, nr))


@fn('t', 'x', 'transpose')
def _t(I, a):
    return transpose(a.x)


@fn('row', 'x', 'row number of each element of a matrix')
def _row(I, a):
    nr, nc = dims(a.x)
    return In([i + 1 for j in range(nc) for i in range(nr)], (nr, nc))


@fn('col', 'x', 'column number of each element of a matrix')
def _col(I, a):
    nr, nc = dims(a.x)
    return In([j + 1 for j in range(nc) for i in range(nr)], (nr, nc))


def cbind(xs):
    xs = [x for x in xs if x is not None and len(x)]
    if not xs:
        raise SError('nothing to bind')
    nr = max(dims(x)[0] if x.dim else len(x) for x in xs)
    mode = max((x.mode for x in xs), key=RANK.get)
    vals, nc = [], 0
    for x in xs:
        x = coerce(x, mode)
        if x.dim:
            if x.dim[0] != nr:
                raise SError('matrices must have the same number of rows')
            vals += x.v
            nc += x.dim[1]
        else:
            vals += [x.v[i % len(x)] for i in range(nr)]
            nc += 1
    return Vec(mode, vals, (nr, nc))


@fn('cbind', '...', 'bind vectors and matrices as columns')
def _cbind(I, a):
    return cbind(a['...'])


@fn('rbind', '...', 'bind vectors and matrices as rows')
def _rbind(I, a):
    return transpose(cbind([transpose(x) if x.dim else x for x in a['...']]))


# -- input and output

@fn('print', '... rowlab= collab=', 'print values; rowlab=, collab= label a matrix', structs=True)
def _print(I, a):
    lab = lambda v: coerce(v, 'character').v if v is not None else None
    for x in a['...']:
        I.write(show(x, lab(a.rowlab), lab(a.collab)))


@fn('read', 'file= len= mode=', 'read numbers (or words) from a file, or from the terminal')
def _read(I, a):
    limit = int(one(a['len'])) if a['len'] else 2000
    items = []
    if a.file is None:
        while len(items) < limit:
            I.write(f'{len(items) + 1}: ')
            line = I.io.readline()
            if not line.strip():
                break
            items += line.split()
        I.write(f'{len(items[:limit])} items read\n')
    else:
        name = one(a.file)
        if not I.shell:
            raise SError(f'cannot open file "{name}"')
        text = I.shell.fs.read(I.shell.path(name))
        if text is None:
            raise SError(f'cannot open file "{name}"')
        items = text.split()
        I.write(f'Read {len(items[:limit])} items\n')
    items = items[:limit]
    want = one(a.mode) if a.mode else None
    if want and str(want).lower().startswith('char'):
        return Ch(items)
    try:
        float(items[0]) if items else 0
    except ValueError:
        return Ch(items)
    return coerce(Ch(items), 'real')


@fn('help', 'name=', 'documentation for a function: help("plot")', quote=True)
def _help(I, a):
    import sdoc                     # the documentation runs its examples in a scratch S
    n = a.name
    if n is None:
        I.write(sdoc.help_index())
        return None
    name = n[1] if n[0] == 'name' else n[1].v[0] if n[0] == 'const' else None
    if name not in BUILTINS:
        raise SError(f'no documentation for "{name}"')
    I.write(sdoc.help_page(name))


def dataset_names(a):
    out = []
    for n, e in a['...']:
        if n is not None:
            raise SError('give the names of datasets')
        if e[0] == 'name':
            out.append(e[1])
        elif e[0] == 'const' and e[1].mode == 'character':
            out += [n.lstrip('$') for n in e[1].v]
        else:
            raise SError('give the names of datasets')
    return out


def pos_of(I, a, default=1):
    p = int(one(I.ev(a.pos))) if a.pos is not None else default
    if p not in (1, 2, 3):
        raise SError('pos must be 1 (working), 2 (save) or 3 (shared)')
    return p


@fn('list', 'pos=', 'names of the datasets on a directory (1 working, 2 save, 3 shared)', quote=True)
def _list(I, a):
    return Ch(sorted(I.db[pos_of(I, a) - 1]))


@fn('rm', '... list= pos= value=', 'remove datasets; returns value=, so a macro can clean up and give a result',
    quote=True)
def _rm(I, a):
    result = I.ev(a.value) if a.value is not None else None    # before its datasets disappear
    db = I.db[pos_of(I, a) - 1]
    names = dataset_names(a)
    if a.list is not None:
        names += coerce(I.ev(a.list), 'character').v
    for n in names:
        if db.pop(n.lstrip('$'), None) is None:
            raise SError(f'"{n}" not found')
    return result


@fn('save', '...', 'store datasets on the save directory: save(x), save(newx=sqrt(x))', quote=True)
def _save(I, a):
    for n, e in a['...']:
        if n is not None:
            I.put(1, n, I.ev(e))
        elif e[0] == 'name':
            I.put(1, e[1], I.lookup(e[1]))
        else:
            raise SError('save needs a dataset name or name=value')


@fn('get', 'name', 'the dataset with this name', structs=True)
def _get(I, a):
    return I.lookup(one(a.name))


@fn('assign', 'name value', 'assign value to the dataset with this name', structs=True)
def _assign(I, a):
    I.store(one(a.name), a.value)


@fn('q', '', 'quit S')
def _q(I, a):
    raise Quit


@fn('rnorm', 'n mean= sd=', 'normal random numbers')
def _rnorm(I, a):
    n = int(one(a.n))
    if not 0 <= n <= MAXLEN:
        raise SError('bad n')
    m, s = (one(a.mean) if a.mean else 0), (one(a.sd) if a.sd else 1)
    return Re([I.rng.gauss(m, s) for _ in range(n)])


@fn('runif', 'n min= max=', 'uniform random numbers')
def _runif(I, a):
    n = int(one(a.n))
    if not 0 <= n <= MAXLEN:
        raise SError('bad n')
    lo, hi = (one(a['min']) if a['min'] else 0), (one(a['max']) if a['max'] else 1)
    return Re([I.rng.uniform(lo, hi) for _ in range(n)])


# -- structures, smoothing and interpolation

@fn('ncomp', 'x', 'number of components of a structure', structs=True)
def _ncomp(I, a):
    return In([len(components(a.x)[0])])


def sorted_pairs(x, y):
    pairs = sorted((p, q) for p, q in zip(x, y) if p is not None and q is not None)
    if not pairs:
        raise SError('no complete (x, y) pairs')
    return [p for p, _ in pairs], [q for _, q in pairs]


@fn('approx', 'x y= xout= method= n= rule=',
    'linear interpolation: an x-y structure of the function at xout= (or n= points)', structs=True)
def _approx(I, a):
    if a.x.mode == 'structure' and a.y is not None and a.xout is None:
        a['xout'], a['y'] = a.y, None       # approx(fit, x), as in the manual's lowess example
    xs, ys = sorted_pairs(*xy(a))
    ux, uy = [], []                         # tied x values share the mean of their y values
    for p, q in zip(xs, ys):
        if ux and p == ux[-1]:
            uy[-1].append(q)
        else:
            ux.append(p)
            uy.append([q])
    uy = [statistics.fmean(v) for v in uy]
    if a.method is not None and one(a.method) != 'linear':
        raise SError('method must be "linear"')
    rule = int(one(a.rule)) if a.rule else 1
    if a.xout is not None:
        xout = num(a.xout)
    else:
        n = int(one(a.n)) if a.n else 50
        if not 1 <= n <= MAXLEN:
            raise SError('bad n')
        xout = [ux[0] + (ux[-1] - ux[0]) * k / max(n - 1, 1) for k in range(n)]
    out = []
    for p in xout:
        if p is None or p < ux[0] or p > ux[-1]:
            out.append(None if p is None or rule == 1 else uy[0] if p < ux[0] else uy[-1])
            continue
        k = bisect.bisect_left(ux, p)
        if ux[k] == p:
            out.append(uy[k])
        else:
            t = (p - ux[k - 1]) / (ux[k] - ux[k - 1])
            out.append(uy[k - 1] + t * (uy[k] - uy[k - 1]))
    return St(x=Re(xout), y=Re(out))


def clowess(x, y, f=2 / 3, iterations=3, delta=0.0, check=lambda: None):
    """Cleveland's robust locally weighted regression (JASA 74, 1979), after his reference
    implementation: x sorted; returns the smoothed y at every x."""
    n = len(x)
    if n < 2:
        return list(y)
    ns = max(2, min(n, int(f * n + 1e-7)))
    fit, rw = [0.0] * n, [1.0] * n
    span = x[-1] - x[0]

    def local(xs, nleft, nright, robust):
        h = max(xs - x[nleft], x[nright] - xs)
        w, j, total = {}, nleft, 0.0
        while j < n:
            r = abs(x[j] - xs)
            if r <= .999 * h:
                w[j] = 1.0 if r <= .001 * h else (1 - (r / h) ** 3) ** 3
                if robust:
                    w[j] *= rw[j]
                total += w[j]
            elif x[j] > xs:
                break
            j += 1
        if total <= 0:
            return None
        w = {k: v / total for k, v in w.items()}
        if h > 0:
            mx = sum(v * x[k] for k, v in w.items())
            c = sum(v * (x[k] - mx) ** 2 for k, v in w.items())
            if c ** .5 > .001 * span:
                b = (xs - mx) / c
                w = {k: v * (b * (x[k] - mx) + 1) for k, v in w.items()}
        return sum(v * y[k] for k, v in w.items())

    for it in range(iterations + 1):
        nleft, nright, last, i = 0, ns - 1, -1, 0
        while True:
            check()
            if nright < n - 1 and x[i] - x[nleft] > x[nright + 1] - x[i]:
                nleft += 1
                nright += 1
                continue
            v = local(x[i], nleft, nright, it > 0)
            fit[i] = y[i] if v is None else v
            if last < i - 1:                      # points skipped within delta: interpolate
                for j in range(last + 1, i):
                    alpha = (x[j] - x[last]) / (x[i] - x[last])
                    fit[j] = alpha * fit[i] + (1 - alpha) * fit[last]
            last, cut = i, x[i] + delta
            i = last + 1
            while i < n and x[i] <= cut:
                if x[i] == x[last]:
                    fit[i] = fit[last]
                    last = i
                i += 1
            i = max(last + 1, i - 1)
            if last >= n - 1:
                break
        if it == iterations:
            break
        res = [abs(p - q) for p, q in zip(y, fit)]
        cmad = 6 * statistics.median(res)
        if cmad < 1e-7 * sum(res) / n:
            break
        rw = [1.0 if r <= .001 * cmad else (1 - (r / cmad) ** 2) ** 2 if r <= .999 * cmad else 0.0
              for r in res]
    return fit


@fn('lowess', 'x y= f= iter= delta=',
    'scatter plot smoothing: an x-y structure of the smooth curve (Cleveland, 1979)', structs=True)
def _lowess(I, a):
    xs, ys = sorted_pairs(*xy(a))
    f = one(a.f) if a.f else 2 / 3
    it = int(one(a.iter)) if a['iter'] else 3
    delta = one(a.delta) if a.delta else 0.0
    if not 0 < f <= 1 or it < 0 or delta < 0:
        raise SError('need 0 < f <= 1, iter >= 0 and delta >= 0')
    fit = clowess(xs, ys, f, it, delta, I.check)
    keep = [k for k in range(len(xs)) if k == 0 or xs[k] != xs[k - 1]]   # duplicates removed (1981 doc)
    return St(x=Re([xs[k] for k in keep]), y=Re([fit[k] for k in keep]))


# -- graphics

def text_arg(a, name, default=''):
    v = a[name]
    return default if v is None else str(coerce(v, 'character').v[0] or '')


def node_label(a, formal):
    e = a['_nodes'].get(formal)
    return e[1] if e and e[0] == 'name' else ''


def xy(a):
    if a.y is None and a.x.mode == 'structure':
        x, y = num(component(a.x, 'x')), num(component(a.x, 'y'))
        if len(x) != len(y):
            raise SError('x and y lengths differ')
        return x, y
    if a.y is None:
        y = num(a.x)
        return list(range(1, len(y) + 1)), y
    x, y = num(a.x), num(a.y)
    if len(x) != len(y):
        raise SError('x and y lengths differ')
    return x, y


def frame(xs, ys, a, zero=False, **labels):
    try:
        return sgraph.Frame(xs, ys, log=text_arg(a, 'log'), main=text_arg(a, 'main'), sub=text_arg(a, 'sub'),
                            xlab=text_arg(a, 'xlab', labels.get('xlab', '')),
                            ylab=text_arg(a, 'ylab', labels.get('ylab', '')), zero=zero)
    except ValueError as e:
        raise SError(str(e))


@fn('printer', '', 'select the line-printer graphics device (plots appear on show)')
def _printer(I, a):
    I.dev, I.frame, I.pending, I.pch = 'printer', None, False, '*'


@fn('tek14', '', 'select the Tektronix 4014 graphics device')
def _tek14(I, a):
    I.dev, I.frame, I.pending, I.pch = 'tek14', None, False, '*'
    I.write(sgraph.osc(sgraph.BLANK, erase=True))


@fn('show', '', 'display the current plot')
def _show(I, a):
    fr = I.need_frame()
    if I.dev == 'printer':
        I.write(sgraph.printer(fr) + '\n')
        I.pending = False
    else:
        I.refresh()


@fn('par', 'pch=', 'graphics parameters: plotting character pch=')
def _par(I, a):
    if a.pch is not None:
        I.pch = text_arg(a, 'pch', '*')[:1] or '*'


@fn('plot', 'x y= type= log= main= sub= xlab= ylab= pch=', 'scatter plot; type="p", "l" or "b"; log="x","y","xy"',
    structs=True)
def _plot(I, a):
    xs, ys = xy(a)
    labels = {'xlab': node_label(a, 'x') if a.y is not None else '' if a.x.mode == 'structure' else 'Index',
              'ylab': node_label(a, 'y' if a.y is not None else 'x')}
    fr = frame(xs, ys, a, **labels)
    t = text_arg(a, 'type', 'p')
    if t in ('l', 'b'):
        fr.items.append(('line', xs, ys))
    if t in ('p', 'b'):
        fr.items.append(('pts', xs, ys, [text_arg(a, 'pch', I.pch)[:1] or '*'] * len(xs)))
    I.new_frame(fr)


@fn('hist', 'x nclass= main= xlab=', 'histogram')
def _hist(I, a):
    v = nona(num(a.x))
    if not v:
        raise SError('no data')
    k = int(one(a.nclass)) if a.nclass else math.ceil(math.log2(len(v)) + 1)
    br = sgraph.pretty(min(v), max(v), max(k, 1))
    if br[0] > min(v):
        br.insert(0, br[0] - (br[1] - br[0] if len(br) > 1 else 1))
    if br[-1] < max(v) or len(br) < 2:
        br.append(br[-1] + (br[1] - br[0] if len(br) > 1 else 1))
    counts = [sum(1 for x in v if (lo < x <= hi) or (i == 0 and x == lo)) for i, (lo, hi) in enumerate(zip(br, br[1:]))]
    fr = frame(br, [0] + counts, a, zero=True, xlab=node_label(a, 'x'))
    for lo, hi, c in zip(br, br[1:], counts):
        fr.items.append(('line', [lo, lo, hi, hi], [0, c, c, 0]))
    I.new_frame(fr)


@fn('barplot', 'height main=', 'bar chart of the heights')
def _barplot(I, a):
    h = nona(num(a.height))
    fr = frame([0.4, len(h) + 0.6], [0] + h, a, zero=True)
    for i, c in enumerate(h, 1):
        fr.items.append(('line', [i - .4, i - .4, i + .4, i + .4], [0, c, c, 0]))
    I.new_frame(fr)


@fn('boxplot', 'x main=', 'box plot: median, hinges and extremes')
def _boxplot(I, a):
    v = sorted(nona(num(a.x)))
    if not v:
        raise SError('no data')
    n = len(v)
    med = statistics.median(v)
    q1, q3 = statistics.median(v[:(n + 1) // 2]), statistics.median(v[n // 2:])
    fr = frame([0.4, 1.6], v, a, ylab=node_label(a, 'x'))
    fr.items += [('line', [.75, 1.25, 1.25, .75, .75], [q1, q1, q3, q3, q1]), ('line', [.75, 1.25], [med, med]),
                 ('line', [1, 1], [v[0], q1]), ('line', [1, 1], [q3, v[-1]]),
                 ('line', [.9, 1.1], [v[0], v[0]]), ('line', [.9, 1.1], [v[-1], v[-1]])]
    I.new_frame(fr)


@fn('points', 'x y= pch=', 'add points to the current plot', structs=True)
def _points(I, a):
    fr = I.need_frame()
    xs, ys = xy(a)
    fr.items.append(('pts', xs, ys, [text_arg(a, 'pch', I.pch)[:1] or '*'] * len(xs)))
    I.refresh()


@fn('lines', 'x y=', 'add connected lines to the current plot', structs=True)
def _lines(I, a):
    fr = I.need_frame()
    fr.items.append(('line', *xy(a)))
    I.refresh()


@fn('abline', 'a= b= h= v=', 'add the line y = a + b*x, or horizontal h= / vertical v= lines')
def _abline(I, a):
    fr = I.need_frame()
    if a.a is not None:
        coef = num(a.a)
        fr.items.append(('abline', coef[0], one(a.b) if a.b else coef[1] if len(coef) > 1 else 0))
    for k in ('h', 'v'):
        if a[k] is not None:
            fr.items += [(k, x) for x in num(a[k]) if x is not None]
    I.refresh()


@fn('text', 'x y labels=', 'write labels at points of the current plot')
def _text(I, a):
    fr = I.need_frame()
    xs, ys = num(a.x), num(a.y)
    labs = coerce(a.labels, 'character').v if a.labels is not None else [str(i) for i in range(1, len(xs) + 1)]
    fr.items.append(('text', xs, ys, [labs[i % len(labs)] for i in range(len(xs))]))
    I.refresh()


@fn('title', 'main= sub= xlab= ylab=', 'add titles to the current plot')
def _title(I, a):
    fr = I.need_frame()
    for k in ('main', 'sub', 'xlab', 'ylab'):
        if a[k] is not None:
            setattr(fr, k, text_arg(a, k))
    I.refresh()


@fn('stem', 'x', 'stem-and-leaf display')
def _stem(I, a):
    v = nona(num(a.x))
    if not v:
        raise SError('no data')
    I.write(sgraph.stem(v) + '\n')


import smacro  # noqa: E402  (registers define, mprint, medit; needs everything above)

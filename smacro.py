"""The S macro processor, after section 4 of the 1981 manual (November 4, 1980).

A macro call ?name(args) is pure text substitution, done before S parses the line, as in
the Software Tools macro processor it was based on. Definitions are written

    MACRO name(arg1, arg2/default/, opt=/default/)
    ...S expressions using the argument names...
    END

and stored by define() as the dataset mac.name, with the argument names rewritten to the
positional $1, $2, ... . Arguments are expanded first; the substituted text is rescanned
for further calls; ?(...) passes text through unscanned.
"""
import re

import s

NAME = re.compile(r'[A-Za-z][A-Za-z0-9.]*')
MAXDEPTH = 60

SYSTEM = """\
MACRO which(condition)
({ $T <- condition;
rm(list="$T", value=(seq($T))[$T])
})
END
MACRO rperm(x)
({$Tx <- x
rm(list="$Tx", value=$Tx[order(runif(len($Tx)))]) })
END
MACRO sample(x,n/?PROMPT(Sample size:)/)
(?rperm(x)[seq(n)])
END
"""


def literal_end(text, i):
    """Index just past the ?(...) literal starting at i."""
    depth, j = 0, i + 1
    while j < len(text):
        if text[j] == '(':
            depth += 1
        elif text[j] == ')':
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise s.Incomplete


def split_args(text, i):
    """Arguments of a call whose '(' is at i: raw texts, leading blanks dropped; and the end index."""
    args, depth, start, j = [], 0, i + 1, i
    while j < len(text):
        c = text[j]
        if text.startswith('?(', j):
            j = literal_end(text, j)
            continue
        if c in '([':                  # brackets too: the manual calls ?reg(pred[,1:4], log(response))
            depth += 1
        elif c in ')]':
            depth -= 1
            if depth == 0:
                args.append(text[start:j])
                return [a.lstrip() for a in args], j + 1
        elif c == ',' and depth == 1:
            args.append(text[start:j])
            start = j + 1
        j += 1
    raise s.Incomplete                 # the call goes on to the next line


def parse_header(header):
    """'MACRO name(a, b/default/, c=/default/)' -> name, [(arg, by_name_only, default or None)]."""
    m = re.match(r'\s*MACRO\s+([A-Za-z][A-Za-z0-9.]*)\s*', header)
    if not m:
        raise s.SError('a macro definition starts with MACRO name')
    name, i, formals = m.group(1), m.end(), []
    if i >= len(header) or header[i] != '(':
        return name, formals
    i += 1
    while True:
        while i < len(header) and header[i] in ' \t\n,':
            i += 1
        if i >= len(header) or header[i] == ')':
            return name, formals
        a = NAME.match(header, i)
        if not a:
            raise s.SError(f'MACRO {name}: bad argument list')
        arg, i = a.group(), a.end()
        by_name = header.startswith('=', i)
        i += by_name
        default = None
        if header.startswith('/', i):
            j = i + 1
            while j < len(header) and header[j] != '/':
                j = literal_end(header, j) if header.startswith('?(', j) else j + 1
            default, i = header[i + 1:j], j + 1
        formals.append((arg, by_name, default))


def positional(line, formals):
    """define's rewriting: each argument name becomes $1, $2, ... (not inside ?(...))."""
    names = [f[0] for f in formals]
    out, i = [], 0
    while i < len(line):
        if line.startswith('?(', i):
            j = literal_end(line, i)
            out.append(line[i:j])
            i = j
            continue
        m = NAME.match(line, i)
        if m and (i == 0 or not (line[i - 1].isalnum() or line[i - 1] == '.')):
            w = m.group()
            out.append(f'${names.index(w) + 1}' if w in names else w)
            i = m.end()
            continue
        out.append(line[i])
        i += 1
    return ''.join(out)


def compile_macros(text):
    """MACRO ... END blocks in text -> {dataset name: character vector}; other lines are ignored."""
    lines, out, i = text.split('\n'), {}, 0
    while i < len(lines):
        if not lines[i].lstrip().startswith('MACRO'):
            i += 1
            continue
        header = lines[i]
        i += 1
        while header.count('(') > header.count(')') and i < len(lines):
            header += '\n' + lines[i]
            i += 1
        name, formals = parse_header(header)
        body = []
        while i < len(lines) and lines[i].strip() != 'END':
            body.append(positional(lines[i], formals))
            i += 1
        if i >= len(lines):
            raise s.SError(f'MACRO {name}: no END')
        i += 1
        out['mac.' + name] = s.Ch([header] + body)
    return out


def system_macros():
    return compile_macros(SYSTEM)


class Expander:
    def __init__(self, interp):
        self.I, self.temp = interp, {}     # temporary ?DEFINE macros last for one expansion

    def expand(self, text, depth=0):
        if depth > MAXDEPTH:
            raise s.SError('macro calls nested too deeply: a macro that calls itself?')
        out, i = [], 0
        while i < len(text):
            if text[i] != '?':
                out.append(text[i])
                i += 1
            elif text.startswith('?(', i):
                j = literal_end(text, i)
                out.append(text[i + 2:j - 1])           # literal: stripped, not scanned
                i = j
            elif m := NAME.match(text, i + 1):
                args, i = None, m.end()
                if text.startswith('(', i):
                    args, i = split_args(text, i)
                out.append(self.call(m.group(), args, depth))
            else:
                out.append('?')
                i += 1
        return ''.join(out)

    def call(self, name, args, depth):
        args = [] if args in (None, ['']) else [self.expand(a, depth + 1) for a in args]
        if name in BUILTIN:
            text = BUILTIN[name](self, args)
        else:
            text = self.substitute(name, args)
        return self.expand(text, depth + 1)              # the result is rescanned

    def substitute(self, name, args):
        if name in self.temp:
            values, extra, body = args, args, self.temp[name]
        else:
            v = next((d['mac.' + name] for d in self.I.db if 'mac.' + name in d), None)
            if v is None:
                raise s.SError(f'macro {name} not defined (no dataset mac.{name})')
            _, formals = parse_header(v.v[0])
            body = '\n'.join(v.v[1:])
            names = [f[0] for f in formals]
            named, rest = {}, []
            for a in args:
                m = re.match(r'([A-Za-z][A-Za-z0-9.]*)\s*=(?!=)', a)
                if m and m.group(1) in names:
                    named[m.group(1)] = a[m.end():].lstrip()
                else:
                    rest.append(a)
            values = []
            for arg, by_name, default in formals:
                if arg in named:
                    values.append(named[arg])
                elif not by_name and rest:
                    values.append(rest.pop(0))
                else:
                    values.append(default or '')
            extra = rest
        return re.sub(r'\$(\d|\*)', lambda m: ','.join(extra) if m.group(1) == '*'
                      else values[int(m.group(1)) - 1] if 0 < int(m.group(1)) <= len(values) else '', body)


# -- built-in macros (manual 4.7)

def arg(args, k, default=''):
    return args[k] if k < len(args) else default


def b_ifelse(e, args):
    for k in range(0, len(args) - 2, 3):
        if args[k].strip() == args[k + 1].strip():
            return args[k + 2]
    return args[-1] if len(args) % 3 == 1 else ''


def b_ifdef(e, args):
    name = arg(args, 0).strip()
    known = name in e.temp or name in BUILTIN or any('mac.' + name in d for d in e.I.db)
    return arg(args, 1) if known else arg(args, 2)


def b_loop(e, args):
    sep, skip, items = ',', None, []
    for a in args[1:]:
        if a.startswith('sep='):
            sep = a[4:]
        elif a.startswith('skip='):
            skip = int(a[5:].strip() or 1)
        else:
            items.append(a)
    string = arg(args, 0)
    m = skip or max((int(k) for k in re.findall(r'\$%(\d)', string)), default=1)
    pieces = []
    for k in range(0, len(items), m):
        group = items[k:k + m]
        pieces.append(re.sub(r'\$%(\d)', lambda g: group[int(g.group(1)) - 1]
                             if int(g.group(1)) <= len(group) else '', string))
    return sep.join(pieces)


def b_define(e, args):
    e.temp[arg(args, 0).strip()] = arg(args, 1)
    return ''


def b_substr(e, args):
    text, start = arg(args, 0), int(arg(args, 1, '1').strip() or 1)
    length = arg(args, 2).strip()
    return text[start - 1:start - 1 + int(length)] if length else text[start - 1:]


def b_sys(e, args):
    if e.I.shell:
        e.I.shell.run_line(arg(args, 0))
    return ''


def b_message(e, args):
    e.I.write(','.join(args) + '\n')
    return ''


def b_fatal(e, args):
    raise s.SError(','.join(args))


def b_prompt(e, args):
    text = ','.join(args)
    e.I.write(text if text.endswith(' ') else text + ' ')
    return e.I.io.readline()


BUILTIN = {'IFELSE': b_ifelse, 'IFDEF': b_ifdef, 'LOOP': b_loop, 'DEFINE': b_define, 'SUBSTR': b_substr,
           'SYS': b_sys, 'MESSAGE': b_message, 'FATAL': b_fatal, 'PROMPT': b_prompt}


def expand(interp, text):
    return Expander(interp).expand(text)


# -- the S functions that make and show macros

def store(I, text, pos):
    found = compile_macros(text)
    if not found:
        raise s.SError('no MACRO ... END definitions found')
    for name, v in found.items():
        I.put(pos - 1, name, v)
        I.write(name + '\n')


@s.fn('define', 'file= pos=', 'define macros from MACRO ... END text in a file, or typed at N> and D>')
def _define(I, a):
    pos = int(s.one(a.pos)) if a.pos else 2
    if pos not in (1, 2):
        raise s.SError('pos must be 1 (working) or 2 (save)')
    if a.file is not None:
        name = s.one(a.file)
        text = I.shell.fs.read(I.shell.path(name)) if I.shell else None
        if text is None:
            raise s.SError(f'cannot open file "{name}"')
    else:
        lines = []
        while True:
            I.write('N> ')
            header = I.io.readline()
            if not header.strip():
                break
            lines.append(header if header.lstrip().startswith('MACRO') else 'MACRO ' + header.strip())
            while True:
                I.write('D> ')
                line = I.io.readline()
                lines.append(line)
                if line.strip() == 'END':
                    break
        if not lines:
            return None
        text = '\n'.join(lines)
    store(I, text, pos)


@s.fn('mprint', 'macro', 'print a macro definition: mprint(mac.which)')
def _mprint(I, a):
    v = a.macro
    if v.mode != 'character' or not v.v or not str(v.v[0]).lstrip().startswith('MACRO'):
        raise s.SError('not a macro definition: give the dataset, e.g. mac.which')
    I.write(''.join(line + '\n' for line in v.v) + 'END\n')


@s.fn('medit', 'macro', 'edit a macro with ed; writing and quitting defines it again', quote=True)
def _medit(I, a):
    import unix                       # here, not at the top: unix imports s, which imports this
    node = a.macro
    if node[0] != 'name' or not node[1].startswith('mac.'):
        raise s.SError('give the macro dataset, e.g. medit(mac.which)')
    pos = next((k for k, d in enumerate(I.db) if node[1] in d), None)
    if pos is None:
        raise s.SError(f'{node[1]} not found')
    if not I.shell:
        raise s.SError('medit needs the shell')
    path = '/tmp/' + node[1]
    try:
        I.shell.fs.write(path, ''.join(line + '\n' for line in I.db[pos][node[1]].v) + 'END\n')
    except unix.NoSpace as e:
        raise s.SError(str(e))
    unix.Ed(I.shell).run(path)
    store(I, I.shell.fs.read(path), min(pos + 1, 2))   # shared macros are edited into the save directory


MANUAL = r"""
MACRO(7)                                                            MACRO(7)

NAME
     macro - writing your own S macros

DESCRIPTION
     A macro extends S with new operations built from S expressions.  It is
     text, not a function: when a line contains ?name, the macro processor
     replaces the call with the text of the macro, the arguments put in
     their places, and only then does S parse and run the line.  Nothing is
     evaluated while a macro expands.  The processor, written by Ed Zayas,
     follows the one in Kernighan and Plauger's Software Tools.

     Macros were popular, and confusing: S users had to keep apart what
     happens when the text expands (macro time) and what happens when S
     runs it (execution time).  In 1988 New S replaced them with functions
     written in S itself, and a utility, MAC.to.FUN, converted old macros.

CALLING A MACRO
          > x <- c(5, 1, 7, 2)
          > ?which(x > 3)
           1 3

     which is one of the macros on the shared directory, with rperm and
     sample.  Arguments go by position or by name, as with functions.

WRITING ONE
     Put the definition in a file, with ed:

          MACRO which(condition)
          ({ $T <- condition;
          rm(list="$T", value=(seq($T))[$T])
          })
          END

     then, in S, define("file") reads every MACRO ... END in the file and
     stores each as a dataset: mac.which, on the save directory (pos=1 for
     the working one).  define() with no file prompts N> for the MACRO line
     and D> for the lines after it; an empty N> line finishes.

     In the body you write the argument names.  define rewrites them as $1,
     $2, ... in order, which mprint(mac.which) shows; you may write $1 and
     $2 yourself.  medit(mac.which) opens the definition in ed; write and
     quit to define it again.

ARGUMENTS
          MACRO reg(x, y, plotfit/TRUE/, main=/Regression/)

     plotfit/TRUE/      a default, the text between slashes
     main=/.../         given only by name: ?reg(a, b, main=Fit)
     $*                 in the body: all arguments not matched, with commas

     A missing argument with no default is empty text.  Arguments are text:
     ?reg(pred[,1], log(resp)) puts pred[,1] and log(resp) into the body,
     even into strings, so main="Regression of y on x" becomes a real title.

     The trap: define rewrites every word that is an argument's name.  With
     an argument called y, $Ts$y would become $Ts$1.  Choose another name,
     or protect the word as a literal: $Ts$?(y).  ?(text) passes text on
     unscanned, with the ?( and ) taken off.

GIVING A RESULT
     A macro meant to act like a function is wrapped in ({ and }): its value
     is the last expression.  If an argument is used twice, store it once in
     a temporary dataset.  By convention their names begin with $T: $Tx,
     $Ty.  The $ keeps any prefix off the name, so the dataset is Tx; do not
     give your own datasets names like Tx.  To clean up and still return a
     result, end with rm: it removes the datasets in list= and returns
     value=.

          MACRO rperm(x)
          ({$Tx <- x
          rm(list="$Tx", value=$Tx[order(runif(len($Tx)))]) })
          END

     Becker's history of S recalls a later ?T(x) that numbered temporaries
     by macro level; the 1981 manual has only the $T convention, so a macro
     that calls another must choose names that cannot meet.

MACRO TIME AND EXECUTION TIME
     if (test) ... is decided when S runs, and can test any value.
     ?IFELSE(a, b, then, else) is decided while the text expands, comparing
     a and b as strings: ?IFELSE(plotfit, TRUE, plot(...)) plots only if the
     argument was written TRUE, and T is not the same string.  Mixing the
     two up was the classic confusion.

BUILT-IN MACROS
     ?IFELSE(a1,b1,c1, a2,b2,c2, ..., d)
                     the first c whose a and b match as strings, else d
     ?IFDEF(name, s1, s2)    s1 if macro name exists, else s2
     ?LOOP(string, a1, a2, ..., sep=, skip=)
                     string once per argument, $%1 replaced by it, joined
                     by sep= (a comma; a newline makes separate lines)
     ?DEFINE(name, text)     a temporary macro, gone when the line is done;
                     its arguments are $1, $2, ... (not a way to define
                     lasting macros, which is define's job)
     ?SUBSTR(string, start, length)    part of a string
     ?MESSAGE(text)  print text      ?FATAL(text)  print it and stop
     ?PROMPT(text)   ask at the terminal; the answer is the expansion, so
                     reg(x/?PROMPT(X matrix:)/) asks for a missing x
     ?SYS(command)   run a UNIX command

AN EXAMPLE THAT COULD HAVE BEEN: BACKFITTING
     Generalized additive models came from Hastie and Tibshirani in the
     mid-1980s and reached S in 1991.  Yet the method, backfitting, needs
     only a smoother, arithmetic and a loop, and S had all three by 1981:
     Cleveland's lowess, published at Bell Laboratories in 1979, as the
     smoother.  The file backfit in your home directory is the macro as a
     1981 user might have written it, had the idea been about.

          $ cat backfit
          $ S
          > define("backfit")
          mac.backfit
          > fitted <- ?backfit(state.x77[,4], state.x77[,5], state.x77[,2])
          > list
          > printer; plot(state.x77[,5], f1, xlab="Murder"); show
          > plot(state.x77[,2], f2, xlab="Income"); show

     Life expectancy is fitted as a level plus a smooth function of the
     murder rate plus a smooth function of income.  Each pass smooths what
     the other function leaves unexplained, then centres it.  It shows the
     old habits: $T temporaries, results left as datasets f1, f2 and fitted,
     rm(list=..., value=fitted) to clean up, and a fixed number of passes,
     passes/4/, rather than a test for convergence, which would mean an if
     at execution time beside ?IFELSE at macro time.

     It does not sort before smoothing.  lowess sorts x itself and returns
     each x once, duplicates removed, so with tied values its result is
     shorter than the data.  approx(lowess(x, r), x)$y reads the smooth off
     at every x in the original order: the manual's own example idiom.

SEE ALSO
     define, mprint, medit and rm in help; man S.
     R. A. Becker and J. M. Chambers, S: A Language and System for Data
     Analysis, Bell Laboratories, 1981, section 4: The S Macro Processor.
     R. A. Becker, A Brief History of S, AT&T Bell Laboratories.
"""

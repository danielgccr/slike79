"""A small UNIX/32V: login, sh, a few Seventh Edition commands and ed, on an in-memory file system."""
import datetime
import posixpath
import re
import shlex

import s
import sdata
import sgraph
import sdoc
import smacro
import typeset
from vt import EOF, Interrupt

BOOT = """
UNIX/32V  Bell Telephone Laboratories, Murray Hill
VAX-11/780  real mem = 2097152

"""

MOTD = """
UNIX/32V Release 1.0 -- Compute S like 1979

S is installed.  Type S to start it and q to leave it.  Try:

    x <- c(1,-1,2,-2,.5); sort(x)
    m <- matrix(read("mydata"), ncol=4, byrow=T)
    printer; plot(m[,2], m[,4], main="Ten States, 1977"); show
    tek14; hist(rnorm(100))

mydata and the other example files are in your home directory: ls.
man lists the commands here; ed is the editor.
man unix1982 replays the demonstrations from the 1982 Bell Labs film.

"""


DOCUMENT = """The UNIX system was written at Bell Laboratories by Ken Thompson and
Dennis Ritchie. Its programs are small tools that each do one job well,
and the shell lets you conect them with pipes, so that a new tool can be
built from old ones without writting a single line of C.
"""

DICTIONARY = ''.join(w + '\n' for w in sorted(
    set(re.findall('[A-Za-z]+', DOCUMENT)) - {'conect', 'writting'}
    | set('a an analysis bell computer connect data file is it of on or program system text to word writing'
          .split())))

EQUATIONS = r""".ps 12
.ce
\fBTypesetting mathematics with eqn\fR
.ps 10
.sp
The roots of the quadratic equation are
.EQ
x = {- b +- sqrt {b sup 2 - 4ac}} over 2a
.EN
and a geometric series sums to
.EQ
sum from i=0 to inf x sup i ~=~ 1 over {1 - x} ~~~~ "for" ~ left | x right | < 1
.EN
A limit:
.EQ
lim from {x -> pi /2} ( tan ~ x ) sup {sin ~ 2x} ~=~ 1
.EN
and the integral of the normal curve:
.EQ
int from {- inf} to inf e sup {- x sup 2 / 2} dx ~=~ sqrt {2 pi}
.EN
"""

BACKFIT = """# backfit: the additive model  resp = a + f1(x1) + f2(x2),  fitted by backfitting.
#
# A "what if".  Generalized additive models came from Hastie and Tibshirani in
# the mid-1980s and reached S only in 1991.  But backfitting needs no more than
# a smoother, arithmetic and a loop, and S had all three by 1981: this is how
# the macro might have looked then.  lowess is Cleveland's smoother (1979).
#
# Define it in S with   define("backfit")   then call
#     fitted <- ?backfit(state.x77[,4], state.x77[,5], state.x77[,2])
# Results come back as datasets f1, f2 and fitted; the value is fitted.
# The argument is called resp, not y: define would turn the y in $Ts$y into $1.

MACRO backfit(resp, x1, x2, passes/4/)
({ $Ty <- resp; $Tx1 <- x1; $Tx2 <- x2     # evaluate each argument once
$Ta <- mean($Ty)
$Tf1 <- 0 * $Ty; $Tf2 <- 0 * $Ty
for(i in 1:passes) {
    # smooth the partial residuals on x1, read the smooth off at every x1
    $Tf1 <- approx(lowess($Tx1, $Ty - $Ta - $Tf2), $Tx1)$y
    $Tf1 <- $Tf1 - mean($Tf1)             # centre: the level belongs to a
    # the same for x2
    $Tf2 <- approx(lowess($Tx2, $Ty - $Ta - $Tf1), $Tx2)$y
    $Tf2 <- $Tf2 - mean($Tf2)
}
f1 <- $Tf1; f2 <- $Tf2
fitted <- $Ta + $Tf1 + $Tf2
rm(list=c("$Ty", "$Tx1", "$Tx2", "$Ta", "$Tf1", "$Tf2"), value=fitted)
})
END
"""

ANALYSIS = """life <- state.x77[,4]
mean(life)
median(life)
sqrt(var(life))
stem(life)
"""

MEMO = r""".TL
Life expectancy in the states, 1977
.AU
A. Student
.AI
Bell Laboratories
.PP
The summaries below were computed by S, run on its own with
\fBS < analysis > results\fR,
and read into this memo by the troff request \fB.so results\fR.
Change the data or the analysis, run S again and format again:
the listing follows.
.DS
.so results
.DE
.PP
That was as far as it went in 1981.
The numbers in the text itself had to be copied in by hand.
"""

REPORT = r""".TL
Life expectancy in the states, 1977
.AU
A. Student
.AI
Bell Laboratories
Murray Hill, New Jersey
.AB
A first look at life expectancy in the 50 states, with the state.x77
data that comes with S.
Every number and listing in this report was computed by S
while the report was being formatted, by spp.
.AE
.SR lo min(state.x77[,4])
.SR hi max(state.x77[,4])
.SR mn round(mean(state.x77[,4]), 2)
.SR sd round(sqrt(var(state.x77[,4])), 2)
.NH
The data
.PP
In 1977 life expectancy ranged from \*(lo to \*(hi years,
with a mean of \*(mn years and a standard deviation of \*(sd.
The summaries and a stem-and-leaf display come straight from S:
.SS
life <- state.x77[,4]
mean(life); median(life)
sqrt(var(life))
stem(life)
.SE
.PP
The standard deviation is the square root of the sample variance
.EQ
s sup 2 ~=~ 1 over {n - 1} sum from i=1 to n ( x sub i - x bar ) sup 2
.EN
which is what var computes.
.NH
Life expectancy and income
.PP
Richer states tend to live longer, up to a point.
A scatter plot with Cleveland's lowess smooth shows the shape:
.SS
income <- state.x77[,2]
tek14
plot(income, life, xlab="Income", ylab="Life expectancy")
lines(lowess(income, life))
.SE
.SR rr round(sum((income-mean(income))*(life-mean(life)))/sqrt(sum((income-mean(income))^2)*sum((life-mean(life))^2)), 2)
.PP
The correlation is only \*(rr: the smooth rises with income,
then levels off, and one rich, outlying state pulls its right end down.
"""

MANPAGES = {'spp': r"""
SPP(1)                                                                SPP(1)

NAME
     spp - what if: an S preprocessor for troff, 1981's R Markdown

SYNOPSIS
     spp file | neqn | nroff -ms | col          the draft, at the terminal
     spp file | eqn | troff -ms                 the typeset proof

DESCRIPTION
     troff already had the pattern.  eqn finds the .EQ ... .EN blocks of a
     document, turns them into plain troff and passes the rest through;
     tbl does the same for tables.  spp is one more preprocessor at the
     front of the pipeline, one that runs S.

          .SS                  S lines, ended by .SE: spp runs them in one S
          life <- state.x77[,4]    session for the whole document and puts
          mean(life)           the listing, with S's output, in their place,
          .SE                  in a constant-width font, without filling
          .SR mn mean(life)    defines the troff string mn as the value S
                               prints; \*(mn in the text inserts it

     A plot cannot go into troff output in 1981: grap, for graphs, came
     only in 1984.  When an .SS block draws on the Tektronix, spp leaves a
     box, "Figure 1: paste up the Tektronix plot here", and the plot was
     glued into the page by hand.  Line-printer plots are text and go in.

     The file report in your home directory is an spp document.  Try

          $ spp report | neqn | nroff -ms | col
          $ spp report | eqn | troff -ms

     The first is the author's draft on the terminal: the ms macros set
     the title, the abstract and numbered headings, nroff fills and
     adjusts, neqn draws the equation in characters.  The second is the
     page from the phototypesetter.

WHAT EXISTED IN 1981
     Nothing ran S inside a document.  The real workflow was S on its own,
     with its output in a file, and troff's .so request to read the file:

          $ cat analysis
          $ S < analysis > results
          $ nroff -ms memo

     memo contains .so results inside a display.  Run S again and format
     again and the listing follows; numbers in the text were copied by
     hand.  make, from 1977, could keep the steps up to date.

WHAT COULD HAVE EXISTED
     spp is a what if.  Every piece it needs was there in 1981: pipes,
     troff and its preprocessors, the -ms macros (by Mike Lesk, shipped
     with the Seventh Edition), and S able to read its commands from a
     file.  Nobody joined them; the idea arrived with Sweave in 2002, and
     later knitr and R Markdown.

NOTES
     nroff marks bold by striking a character twice and italics by
     underlining it, with backspaces.  A VT100 shows only the last
     character, so the marks vanish; col -b removes them for a file.
     tbl is not on this machine.

SEE ALSO
     eqn, neqn, troff, nroff, col, S; man unix1982 for the 1982 film.
""",
'unix1982': r"""
UNIX1982(7)                                                       UNIX1982(7)

NAME
     unix1982 - the 1982 Bell Labs film, and its demonstrations

DESCRIPTION
     In 1982 Bell Laboratories made a film about the UNIX system, later
     released as "AT&T Archives: The UNIX Operating System" (27 minutes).
     Brian Kernighan, Dennis Ritchie, Ken Thompson, Alfred Aho, Stu Feldman
     and Lorinda Cherry explain UNIX as a programming environment built from
     very few primitives: a hierarchical file system whose files are just
     sequences of bytes, programs that are just files, and a shell, a
     language for combining programs.  Everything else comes from combining
     them.

     This machine replays the film's two demonstrations.  Your home
     directory holds the files they use: document, dictionary, equations.

THE SPELLING CHECKER (Brian Kernighan)
     Build the checker one stage at a time and look at each result:

          cat document
          tr -cs A-Za-z '\012' < document
          tr -cs A-Za-z '\012' < document | sort
          tr -cs A-Za-z '\012' < document | sort | uniq
          tr -cs A-Za-z '\012' < document | sort | uniq | comm -23 - dictionary

     tr turns every run of non-letters into one newline, so each word is on
     a line of its own; sort and uniq leave each word once; comm -23 prints
     the words that are not in the dictionary.  No program was changed and
     no C was written.

     012 is the ASCII code for newline.  The article prints the first stage
     with '\n', which is how a modern tr spells it; Seventh Edition tr knows
     only octal escapes, so here, as in 1979, '\n' is just the letter n.
     Try it and watch the words run together.

     Keep the pipeline as a shell procedure, a command like any other:

          ed spell
          a
          tr -cs A-Za-z '\012' < $1 | sort | uniq | comm -23 - dictionary
          .
          w
          q
          chmod +x spell
          spell document

TYPESETTING (Lorinda Cherry)
     equations is a troff document with eqn displays.  Look at the source,
     at the troff that eqn turns it into, and at the typeset page:

          cat equations
          eqn equations
          eqn equations | troff

     troff without eqn sets the equations as plain words:

          troff equations

     The page appears as a phototypesetter proof over the terminal; press
     Esc or click to put it away.

KEYS
     The switch under the terminal chooses the line discipline.  1979 is the
     Seventh Edition driver: # erases, @ kills the line, DEL (the Delete key)
     interrupts, and nothing is rubbed out on screen.  Users remapped erase
     with stty erase '^h' (quoted, because ^ is also a pipe to sh), and S
     users had to, since # starts an S comment.

SEE ALSO
     sh, ed, tr, sort, uniq, comm, eqn, troff, stty, S; man spp for reports
     https://sparsenotes.com/posts/2026/07/unix-att-archives-1982/
"""}


def year_1979(now=None):
    now = now or datetime.datetime.now()
    try:
        return now.replace(year=1979)
    except ValueError:                  # Feb 29
        return now.replace(year=1979, day=28)


def mydata():
    """The ten-state data of the manual's example session: population, income, illiteracy, life expectancy."""
    x = sdata.STATE_X77
    return ''.join(' '.join(f'{x[r + 50 * c]:g}' for c in range(4)) + '\n' for r in range(10))


FS_LIMIT = 2_000_000          # bytes of files per visitor: this demo's disk
OUTPUT_LIMIT = 4_000_000      # characters one command may print


class NoSpace(Exception):
    def __str__(self):
        return 'No space left on device'        # V7's words for ENOSPC


class FS:
    # ponytail: lost on disconnect; persist to disk keyed by a cookie when wanted
    def __init__(self):
        self.files, self.dirs, self.exec = {}, {'/'}, set()

    def read(self, p):
        return self.files.get(p)

    def write(self, p, text, append=False):
        if posixpath.dirname(p) not in self.dirs or p in self.dirs:
            return False
        new = (self.files.get(p, '') if append else '') + text
        if sum(map(len, self.files.values())) - len(self.files.get(p, '')) + len(new) > FS_LIMIT:
            raise NoSpace
        self.files[p] = new
        return True

    def remove(self, p):
        self.exec.discard(p)
        return self.files.pop(p, None)

    def mkdir(self, p):
        if posixpath.dirname(p) not in self.dirs or p in self.dirs or p in self.files:
            return False
        self.dirs.add(p)
        return True

    def ls(self, d):
        return sorted({posixpath.basename(p) for p in (*self.files, *self.dirs)
                       if p != '/' and posixpath.dirname(p) == d})


def seed(fs):
    for d in ('/bin', '/etc', '/tmp', '/usr', '/usr/dict', '/usr/bin'):
        fs.mkdir(d)
    for c in CMDS:
        fs.write('/bin/' + c, '')
        fs.exec.add('/bin/' + c)
    fs.write('/etc/motd', MOTD)
    fs.write('/etc/passwd', 'root::0:1::/:\nbin::3:4::/bin:\nsys::2:3::/usr/sys:\n')
    fs.write('/usr/dict/words', DICTIONARY)


def seed_home(fs, home):
    """The example files every login finds at home, root's home / included; ones already there are kept."""
    for name, text in (('mydata', mydata()), ('document', DOCUMENT), ('dictionary', DICTIONARY),
                       ('equations', EQUATIONS), ('backfit', BACKFIT), ('report', REPORT),
                       ('analysis', ANALYSIS), ('memo', MEMO)):
        path = posixpath.join(home, name)
        if fs.read(path) is None:
            fs.write(path, text)


CMDS = {}


class CmdError(Exception):
    pass


def cmd(name, doc):
    def deco(f):
        CMDS[name] = (f, doc)
        return f
    return deco


def lines(text):
    out = text.split('\n')
    if out and out[-1] == '':
        out.pop()
    return out


def read_input(sh, names, stdin):
    """Concatenated input: the named files, '-' for standard input, none at all for standard input.
    Standard input is the pipe, or the terminal up to ^D."""
    out = []
    for n in names or ['-']:
        if n != '-':
            text = sh.fs.read(sh.path(n))
            if text is None:
                raise CmdError(f"can't open {n}")
            out.append(text)
        elif stdin is not None:
            out.append(stdin)
        else:
            typed = []
            try:
                while True:
                    typed.append(sh.tty.readline() + '\n')
            except EOF:
                pass
            out.append(''.join(typed))
    return ''.join(out)


def uncomment(line):
    """sh comments start with # only at the beginning of a word, outside quotes."""
    quote = None
    for i, c in enumerate(line):
        if quote:
            quote = None if c == quote else quote
        elif c in '\'"':
            quote = c
        elif c == '#' and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


class Shell:
    def __init__(self, tty, fs, user):
        self.tty, self.fs, self.user = tty, fs, user
        self.home = '/' if user == 'root' else '/usr/' + user
        self.cwd = self.home
        self.login_time = year_1979()
        self.argv = ['sh']

    def path(self, p):
        return posixpath.normpath(posixpath.join(self.cwd, p))

    def run(self):
        prompt = '# ' if self.user == 'root' else '$ '
        while True:
            try:
                self.tty.write(prompt)
                line = self.tty.readline()
            except Interrupt:
                continue
            except EOF:
                return
            if self.run_line(line) == 'logout':
                return

    def param(self, m):
        k = m.group(1)
        if k == '#':
            return str(len(self.argv) - 1)
        if k == '*':
            return ' '.join(self.argv[1:])
        return self.argv[int(k)] if int(k) < len(self.argv) else ''

    def run_line(self, line, w=None, stdin=None, depth=0):
        """sh grammar: cmd args <in >out >>out, joined by | into pipelines and by ; into lists.
        Pipelines run one stage after another, each stage's output buffered for the next."""
        # ponytail: $n is substituted before quoting, and a quoted ; or | still splits; real sh grammar if anyone asks
        w = w or self.tty.write
        try:
            lex = shlex.shlex(re.sub(r'\$([0-9*#])', self.param, uncomment(line)), posix=True,
                              punctuation_chars=';|^<>')
            lex.whitespace_split = True
            lex.commenters = ''
            toks = list(lex)
        except ValueError:
            self.tty.write('syntax error\n')
            return
        cmds, cur = [], []
        for t in toks + [';']:
            if t == ';':
                if cur:
                    cmds.append(cur)
                cur = []
            else:
                cur.append(t)
        try:
            for c in cmds:
                stages, stage = [], []
                for t in c + ['|']:
                    if t in ('|', '^'):             # ^ is the older spelling of |
                        stages.append(stage)
                        stage = []
                    else:
                        stage.append(t)
                if not all(stages):
                    self.tty.write('syntax error\n')
                    return
                if self.pipeline(stages, w, stdin, depth) == 'logout':
                    return 'logout'
        except Interrupt:
            if depth:
                raise               # stop the enclosing shell procedure too

    def pipeline(self, stages, w, stdin, depth):
        data = stdin
        for k, stage in enumerate(stages):
            words, inp, out, append = [], None, None, False
            it = iter(stage)
            for t in it:
                if t in ('<', '>', '>>'):
                    target = next(it, None)
                    if target is None or target in ('<', '>', '>>'):
                        self.tty.write('syntax error\n')
                        return
                    if t == '<':
                        inp = target
                    else:
                        out, append = target, t == '>>'
                else:
                    words.append(t)
            if inp is not None:
                data = self.fs.read(self.path(inp))
                if data is None:
                    self.tty.write(f'{inp}: cannot open\n')
                    return
            last = k == len(stages) - 1
            buf = []
            if words and words[0] in ('exit', 'logout'):
                return 'logout'
            if words:
                self.exec(words, buf.append if out or not last else w, data, depth)
            if out:
                try:
                    if not self.fs.write(self.path(out), ''.join(buf), append):
                        self.tty.write(f'{out}: cannot create\n')
                except NoSpace as e:
                    self.tty.write(f'{out}: {e}\n')
            data = '' if out else ''.join(buf)

    def exec(self, words, w, stdin, depth):
        name, sent = words[0], 0
        printing = w

        def w(text):
            nonlocal sent
            sent += len(text)
            if sent > OUTPUT_LIMIT:
                raise CmdError('output stopped at 4 MB, the limit for one command here')
            printing(text)

        p = self.path(name) if '/' in name else None
        if p and posixpath.dirname(p) in ('/bin', '/usr/bin') and posixpath.basename(p) in CMDS:
            name, p = posixpath.basename(p), None
        try:
            if p is None and name in CMDS:
                CMDS[name][0](self, words[1:], w, stdin)
                return
            cands = [p] if p else [self.path(name), '/bin/' + name, '/usr/bin/' + name]
            path = next((c for c in cands if c in self.fs.files), None)
            if path is None:
                self.tty.write(f'{name}: not found\n')
            elif path not in self.fs.exec:
                self.tty.write(f'{name}: cannot execute\n')
            else:
                self.procedure(path, words[1:], w, stdin, depth)
        except (CmdError, NoSpace) as e:
            self.tty.write(f'{name}: {e}\n')

    def procedure(self, path, args, w, stdin, depth):
        """A shell procedure: a file of commands, run with $0..$9 set; indistinguishable from a program."""
        if depth > 16:
            raise CmdError('procedures nested too deeply')
        saved, self.argv = self.argv, [posixpath.basename(path)] + args
        try:
            for line in lines(self.fs.read(path)):
                self.tty.check()
                if self.run_line(line, w, stdin, depth + 1) == 'logout':
                    break
        finally:
            self.argv = saved


@cmd('ls', 'list a directory (-l for details)')
def _ls(sh, args, w, stdin):
    long = '-l' in args
    names = [a for a in args if not a.startswith('-')] or ['.']
    for n in names:
        p = sh.path(n)
        if p in sh.fs.dirs:
            entries = [(e, posixpath.join(p, e)) for e in sh.fs.ls(p)]
        elif p in sh.fs.files:
            entries = [(n, p)]
        else:
            w(f'{n} not found\n')
            continue
        if long:
            w(f'total {len(entries)}\n')
        for e, full in entries:
            if long:
                isdir = full in sh.fs.dirs
                size = 512 if isdir else len(sh.fs.files[full])
                stamp = sh.login_time.strftime('%b %e %H:%M')
                mode = 'drwxr-xr-x' if isdir else '-rwxr-xr-x' if full in sh.fs.exec else '-rw-r--r--'
                w(f'{mode} 1 {sh.user:<8}{size:>6} {stamp} {e}\n')
            else:
                w(e + '\n')


@cmd('cat', 'print files (no file, or -: standard input)')
def _cat(sh, args, w, stdin):
    for a in args or ['-']:
        try:
            w(read_input(sh, [a], stdin))
        except CmdError as e:
            sh.tty.write(f'cat: {e}\n')


@cmd('echo', 'print the arguments')
def _echo(sh, args, w, stdin):
    w(' '.join(args) + '\n')


@cmd('rm', 'remove files')
def _rm(sh, args, w, stdin):
    for a in args:
        if sh.fs.remove(sh.path(a)) is None:
            sh.tty.write(f'rm: {a} nonexistent\n')


def _copy(sh, args, move):
    name = 'mv' if move else 'cp'
    if len(args) != 2:
        sh.tty.write(f'Usage: {name} f1 f2\n')
        return
    src, dst = sh.path(args[0]), sh.path(args[1])
    if dst in sh.fs.dirs:
        dst = posixpath.join(dst, posixpath.basename(src))
    text = sh.fs.read(src)
    if text is None:
        sh.tty.write(f'{name}: cannot open {args[0]}\n')
    elif not sh.fs.write(dst, text):
        sh.tty.write(f'{name}: cannot create {args[1]}\n')
    elif move and dst != src:
        if src in sh.fs.exec:
            sh.fs.exec.add(dst)
        sh.fs.remove(src)


@cmd('cp', 'copy a file')
def _cp(sh, args, w, stdin):
    _copy(sh, args, False)


@cmd('mv', 'move or rename a file')
def _mv(sh, args, w, stdin):
    _copy(sh, args, True)


@cmd('mkdir', 'make a directory')
def _mkdir(sh, args, w, stdin):
    for a in args:
        if not sh.fs.mkdir(sh.path(a)):
            sh.tty.write(f'mkdir: cannot make {a}\n')


@cmd('pwd', 'print the working directory')
def _pwd(sh, args, w, stdin):
    w(sh.cwd + '\n')


@cmd('cd', 'change directory (no argument: home)')
def _cd(sh, args, w, stdin):
    p = sh.path(args[0]) if args else sh.home
    if p in sh.fs.dirs:
        sh.cwd = p
    else:
        sh.tty.write(f'{args[0]}: bad directory\n')


@cmd('wc', 'count lines, words and characters')
def _wc(sh, args, w, stdin):
    for a in args or ['-']:
        t = read_input(sh, [a], stdin)
        w(f'{t.count(chr(10)):7}{len(t.split()):8}{len(t):8}' + (f' {a}' if a != '-' else '') + '\n')


@cmd('clear', 'clear the screen and the scrollback, as on Linux')
def _clear(sh, args, w, stdin):
    w('\x1b[H\x1b[2J\x1b[3J')       # home, erase screen, erase saved lines


@cmd('date', 'print the date')
def _date(sh, args, w, stdin):
    w(year_1979().strftime('%a %b %e %H:%M:%S EST %Y') + '\n')


@cmd('who', 'who is logged in')
def _who(sh, args, w, stdin):
    w(f'{sh.user:<8} tty00   {sh.login_time.strftime("%b %e %H:%M")}\n')


@cmd('tr', "translate characters: tr [-cds] set1 set2, e.g. tr -cs A-Za-z '\\012'")
def _tr(sh, args, w, stdin):
    flags = ''
    while args and args[0].startswith('-') and len(args[0]) > 1:
        flags += args[0][1:]
        args = args[1:]
    s1 = tr_set(args[0]) if args else []
    s2 = tr_set(args[1]) if len(args) > 1 else []
    in1, in2 = set(s1), set(s2)
    table = {c: s2[min(k, len(s2) - 1)] for k, c in enumerate(s1)} if s2 else {}
    out, last = [], None
    for ch in read_input(sh, [], stdin):
        hit = (ch in in1) != ('c' in flags)
        if 'd' in flags:
            if hit:
                continue
            o = ch
        elif hit and s2:
            o = s2[-1] if 'c' in flags else table[ch]
        else:
            o = ch
        if 's' in flags and o == last and o in in2:
            continue
        out.append(o)
        last = o
    w(''.join(out))


def tr_set(s):
    """tr character set as V7 nextc() reads it: ranges a-z, and a backslash takes 1-3 octal
    digits (\\012 is newline) or else stands for the next character, so \\n is just n."""
    chars, i = [], 0

    def one(i):
        if s[i] == '\\' and i + 1 < len(s):
            m = re.match(r'[0-7]{1,3}', s[i + 1:])
            if m:
                return chr(int(m.group(), 8)), i + 1 + m.end()
            return s[i + 1], i + 2
        return s[i], i + 1

    while i < len(s):
        c, i = one(i)
        if i < len(s) - 1 and s[i] == '-':
            d, i = one(i + 1)
            chars += [chr(k) for k in range(ord(c), ord(d) + 1)]
        else:
            chars.append(c)
    return chars


@cmd('sort', 'sort lines: -r reverse, -n numeric, -f fold case, -u unique')
def _sort(sh, args, w, stdin):
    flags = ''.join(a[1:] for a in args if a.startswith('-') and len(a) > 1)
    files = [a for a in args if not (a.startswith('-') and len(a) > 1)]
    data = lines(read_input(sh, files, stdin))

    def key(x):
        if 'n' in flags:
            m = re.match(r'\s*-?\d+(\.\d*)?', x)
            return (float(m.group()) if m else 0.0, x)
        return x.lower() if 'f' in flags else x

    data.sort(key=key, reverse='r' in flags)
    if 'u' in flags:
        data = [x for k, x in enumerate(data) if k == 0 or key(x) != key(data[k - 1])]
    w(''.join(x + '\n' for x in data))


@cmd('uniq', 'drop repeated adjacent lines: -c count, -d only repeated, -u only unique')
def _uniq(sh, args, w, stdin):
    flags = ''.join(a[1:] for a in args if a.startswith('-') and len(a) > 1)
    files = [a for a in args if not (a.startswith('-') and len(a) > 1)]
    data, k = lines(read_input(sh, files[:1], stdin)), 0
    while k < len(data):
        j = k
        while j + 1 < len(data) and data[j + 1] == data[k]:
            j += 1
        n = j - k + 1
        if not ('d' in flags and n == 1 or 'u' in flags and n > 1):
            w((f'{n:4} ' if 'c' in flags else '') + data[k] + '\n')
        k = j + 1


@cmd('comm', 'lines only in file1, only in file2, in both: comm [-123] file1 file2 (- is standard input)')
def _comm(sh, args, w, stdin):
    flags = args[0][1:] if args and args[0].startswith('-') and len(args[0]) > 1 else ''
    files = args[1:] if flags else args
    if len(files) != 2:
        raise CmdError('usage: comm [-123] file1 file2')
    a, b = (lines(read_input(sh, [f], stdin)) for f in files)
    i = j = 0
    while i < len(a) or j < len(b):
        if j >= len(b) or (i < len(a) and a[i] < b[j]):
            col, text, i = 1, a[i], i + 1
        elif i >= len(a) or b[j] < a[i]:
            col, text, j = 2, b[j], j + 1
        else:
            col, text, i, j = 3, a[i], i + 1, j + 1
        if str(col) not in flags:
            w('\t' * sum(1 for c in range(1, col) if str(c) not in flags) + text + '\n')


@cmd('chmod', 'change mode: chmod +x file, or an octal mode such as 755')
def _chmod(sh, args, w, stdin):
    if len(args) < 2:
        raise CmdError('usage: chmod mode file ...')
    mode = args[0]
    if re.fullmatch(r'[0-7]{1,4}', mode):
        on = bool(int(mode, 8) & 0o111)
    elif re.fullmatch(r'[ugoa]*[-+=][rwxst]*', mode):
        on = ('x' in mode) if '=' in mode else (None if 'x' not in mode else '+' in mode)
    else:
        raise CmdError('invalid mode')
    for f in args[1:]:
        p = sh.path(f)
        if p not in sh.fs.files:
            sh.tty.write(f"chmod: can't change {f}\n")
        elif on:
            sh.fs.exec.add(p)
        elif on is False:
            sh.fs.exec.discard(p)


@cmd('stty', "terminal settings: stty, stty erase '^h', stty kill '^u'")
def _stty(sh, args, w, stdin):
    t, ch = sh.tty, sh.tty.chars
    if not args:
        if t.mode == 'modern':
            w('modern line discipline: Backspace erases, ^U kills, ^C interrupts, arrows recall history\n'
              f'with the 1979 switch: erase = {ctrl(ch["erase"])}; kill = {ctrl(ch["kill"])}; '
              f'intr = {ctrl(ch["intr"])}\n')
        else:
            w(f'speed 9600 baud\nerase = {ctrl(ch["erase"])}; kill = {ctrl(ch["kill"])}\n')
        return
    it = iter(args)
    for a in it:
        if a not in ch:
            raise CmdError(f'unknown mode: {a}')
        v = next(it, None)
        if v is None or not re.fullmatch(r'\^.|.', v):
            raise CmdError(f"{a} needs one character, such as '^h' (quoted: ^ is a pipe)")
        ch[a] = '\x7f' if v == '^?' else chr(ord(v[1].upper()) - 64) if len(v) == 2 else v


def ctrl(c):
    return '^?' if c == '\x7f' else '^' + chr(ord(c) + 64) if c < ' ' else c


@cmd('sh', 'the shell: sh file [args] runs a shell procedure; sh alone starts a new shell')
def _sh(sh, args, w, stdin):
    if not args:
        sh.run()
        return
    p = sh.path(args[0])
    if p not in sh.fs.files:
        raise CmdError(f'{args[0]}: cannot open')
    sh.procedure(p, args[1:], w, stdin, 0)


@cmd('eqn', 'typeset mathematics: eqn files | troff')
def _eqn(sh, args, w, stdin):
    try:
        w(typeset.eqn(read_input(sh, args, stdin)))
    except ValueError as e:
        raise CmdError(str(e))


def formatter_input(sh, args, stdin):
    """Flags (-ms) and the text, with .so requests replaced by the files they name."""
    flags = [a for a in args if a.startswith('-') and len(a) > 1]
    files = [a for a in args if a not in flags]
    return '-ms' in flags, soelim(sh, read_input(sh, files, stdin))


def soelim(sh, text, depth=0):
    out = []
    for line in text.split('\n'):
        m = re.match(r'\.so\s+(\S+)', line)
        if not m:
            out.append(line)
            continue
        included = sh.fs.read(sh.path(m.group(1)))
        if included is None:
            raise CmdError(f"can't open {m.group(1)}")
        if depth > 8:
            raise CmdError('.so nested too deeply')
        out.append(soelim(sh, included.rstrip('\n'), depth + 1))
    return '\n'.join(out)


@cmd('troff', 'typeset text on the phototypesetter (the proof opens over the terminal); -ms for the ms macros')
def _troff(sh, args, w, stdin):
    macros, text = formatter_input(sh, args, stdin)
    page = typeset.troff(text, macros)
    if len(page) > OUTPUT_LIMIT:
        raise CmdError('too long for the phototypesetter here')
    sh.tty.write(typeset.osc(page))


@cmd('nroff', 'format text for the terminal or line printer; -ms for the ms macros')
def _nroff(sh, args, w, stdin):
    macros, text = formatter_input(sh, args, stdin)
    w(typeset.nroff(text, macros))


@cmd('neqn', 'eqn for nroff: equations drawn in characters: neqn files | nroff')
def _neqn(sh, args, w, stdin):
    try:
        w(typeset.neqn(read_input(sh, [a for a in args if not a.startswith('-')], stdin)))
    except ValueError as e:
        raise CmdError(str(e))


@cmd('col', 'filter for nroff output; -b removes backspaced overstrikes')
def _col(sh, args, w, stdin):
    text = read_input(sh, [a for a in args if not a.startswith('-')], stdin)
    if '-b' in args:
        while re.search('.\b', text):
            text = re.sub('[^\b]\b', '', text, count=0)
    w(text)


OSC_TEK = re.compile(r'\x1b\]1979;(?:E;)?([^\x07]*)\x07')


class Transcript:
    """S reading a block of lines, its output collected with each line echoed after its prompt."""

    def __init__(self, tty):
        self.tty, self.lines, self.out = tty, [], []

    def write(self, text):
        self.out.append(text)

    def check(self):
        self.tty.check()

    def readline(self):
        if not self.lines:
            raise EOF
        line = self.lines.pop(0)
        self.out.append(line + '\n')
        return line


def figure_box(n):
    caption = f'Figure {n}: paste up the Tektronix plot here'
    inner = len(caption) + 8
    rows = ['+' + '-' * inner + '+', '|' + ' ' * inner + '|', '|' + caption.center(inner) + '|',
            '|' + ' ' * inner + '|', '+' + '-' * inner + '+']
    return ['.sp', '.nf', '.ft CW', '.ce 5', *rows, '.ft R', '.fi', '.sp']


def spp(sh, text):
    """What if: run the .SS ... .SE blocks of a troff document through one S session and put
    each listing with its output in their place; .SR xx expr defines the string \\*(xx."""
    io = Transcript(sh.tty)
    interp = s.Interp(io, sh)
    out, figures, lines, i = [], 0, text.split('\n'), 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.strip() == '.SS':
            block = []
            while i < len(lines) and lines[i].strip() != '.SE':
                block.append(lines[i])
                i += 1
            i += 1
            io.lines, io.out = block, []
            interp.repl()
            shown = ''.join(io.out).removesuffix('> ')
            pictures = [p for p in OSC_TEK.findall(shown) if p != sgraph.BLANK]
            shown = OSC_TEK.sub('', shown).rstrip('\n')
            out += ['.sp 0.5', '.nf', '.ft CW'] + ['\\&' + x.replace('\\', '\\e') for x in shown.split('\n')]
            out += ['.ft R', '.fi', '.sp 0.5']
            if pictures:                       # 1981: no way to put a plot into troff output
                figures += 1
                out += figure_box(figures)
        elif line.startswith('.SR'):
            parts = line.split(None, 2)
            if len(parts) < 3:
                raise CmdError(f'bad .SR line: {line}')
            io.lines, io.out = [], []
            try:
                interp.run(parts[2])
                value = ' '.join(tok.strip('"') for tok in ''.join(io.out).split())
            except s.SError as e:
                sh.tty.write(f'spp: .SR {parts[1]}: {e}\n')
                value = '??'
            out.append(f'.ds {parts[1]} ' + value.replace('\\', '\\e'))
        else:
            out.append(line)
    return '\n'.join(out) + '\n'


@cmd('spp', 'what if: run the S blocks (.SS ... .SE) of a troff document: spp report | neqn | nroff -ms')
def _spp(sh, args, w, stdin):
    w(spp(sh, read_input(sh, args, stdin)))


class Batch:
    """S < file: commands come from the file, output goes wherever sh sends it."""

    def __init__(self, text, w, tty):
        self.lines, self.w, self.tty = lines(text), w, tty

    def write(self, text):
        self.w(text)

    def check(self):
        self.tty.check()

    def readline(self):
        if not self.lines:
            raise EOF
        return self.lines.pop(0)


@cmd('S', 'the S system for data analysis and graphics; S < file runs the commands in file')
def _S(sh, args, w, stdin):
    if stdin is None:
        s.Interp(sh.tty, sh).repl()
        return
    interp = s.Interp(Batch(stdin, w, sh.tty), sh)
    interp.prompts = False           # ponytail: whether 1981 S printed prompts here is not in the manual
    interp.repl()


@cmd('ed', 'the text editor: ed [file]')
def _ed(sh, args, w, stdin):
    Ed(sh).run(args[0] if args else '')


@cmd('man', 'print a manual entry: man [command]')
def _man(sh, args, w, stdin):
    if not args:
        for k, (_, doc) in sorted(CMDS.items()):
            w(f'{k:<8}{doc}\n')
        w(f'{"logout":<8}leave (also exit, ^D)\n')
        w('\nAlso: man S, the S language; man macro, writing S macros; man spp, reports;\n'
          '      man unix1982, the 1982 Bell Labs film and its demonstrations.\n')
    for a in args:
        if a in MANPAGES:
            w(MANPAGES[a])
        elif a in ('macro', 'macros'):
            w(smacro.MANUAL)
        elif a == 'ed':
            w('ed [file]\n' + ''.join(f'    {k:<12}{v}\n' for k, v in ED_HELP))
        elif a == 'S':
            w(sdoc.manual())
        elif a in CMDS:
            w(f'{a} - {CMDS[a][1]}\n')
        else:
            w(f'No manual entry for {a}.\n')


# ---------------------------------------------------------------- ed

ED_HELP = [
    ('a i c', 'append, insert, change: type lines, end with a lone "."'),
    ('d', 'delete lines'),
    ('p n l', 'print lines (n: numbered, l: unambiguously)'),
    ('=', 'print a line number ($ by default)'),
    ('s/re/rep/g', 'substitute (& is the match, \\1 a group)'),
    ('g/re/cmd v/re/cmd', 'run cmd on lines that match (v: that do not)'),
    ('m t j', 'move, copy (t) after an address, join lines'),
    ('w r e f', 'write, read, edit a file; set the file name'),
    ('u', 'undo the last change'),
    ('q Q', 'quit (Q: even if not written)'),
    ('!cmd', 'run a shell command'),
    ('h', 'explain the last ?'),
    ('addresses', '. $ n /re/ ?re? +n -n  x,y  ,(all)  ;'),
]


class EdError(Exception):
    pass


class Line(str):
    """Distinct object per line, so g/re/ can follow marked lines through deletions."""
    __slots__ = ()


def bre(p):
    """Seventh Edition basic regular expression -> Python re."""
    out, i = '', 0
    while i < len(p):
        c = p[i]
        if c == '\\' and i + 1 < len(p):
            n = p[i + 1]
            out += {'(': '(', ')': ')'}.get(n) or ('\\' + n if n.isdigit() else re.escape(n))
            i += 2
        elif c == '[':
            j = i + 1
            if j < len(p) and p[j] == '^':
                j += 1
            if j < len(p) and p[j] == ']':
                j += 1
            while j < len(p) and p[j] != ']':
                j += 1
            if j >= len(p):
                raise EdError('unbalanced [')
            out += p[i:j + 1].replace('\\', '\\\\')
            i = j + 1
        else:
            out += c if c in '.*^$' else re.escape(c)
            i += 1
    try:
        return re.compile(out)
    except re.error as e:
        raise EdError(f'bad regular expression: {e}')


def subst(rep):
    def f(m):
        out, i = '', 0
        while i < len(rep):
            c = rep[i]
            if c == '\\' and i + 1 < len(rep):
                n = rep[i + 1]
                out += (m.group(int(n)) or '') if n.isdigit() and int(n) <= (m.re.groups or 0) else n
                i += 2
            else:
                out += m.group(0) if c == '&' else c
                i += 1
        return out
    return f


def delimited(s, i, d):
    """Text up to an unescaped delimiter d; returns (text, index after it)."""
    out = ''
    while i < len(s) and s[i] != d:
        if s[i] == '\\' and i + 1 < len(s):
            out += s[i + 1] if s[i + 1] == d else s[i:i + 2]
            i += 2
        else:
            out += s[i]
            i += 1
    return out, i + 1


class Ed:
    def __init__(self, sh):
        self.sh, self.tty = sh, sh.tty
        self.buf, self.cur, self.fname = [], 0, ''
        self.dirty = self.warned = self.in_g = False
        self.undo, self.last_re, self.err = None, None, ''

    def w(self, text):
        self.tty.write(text)

    def run(self, fname):
        if fname:
            self.fname = fname
            try:
                self.buf = self.load(fname)
                self.cur = len(self.buf)
            except EdError as e:
                self.err = str(e)
                self.w(f'?{fname}\n')
        while True:
            try:
                line = self.tty.readline()
            except Interrupt:
                self.w('?\n')
                continue
            except EOF:
                line = 'q'
            try:
                warned = self.warned
                if self.command(line) == 'quit':
                    return
                if warned:
                    self.warned = False
            except EdError as e:
                self.err = str(e)
                self.w('?\n')

    # -- helpers
    def regex(self, pat):
        if pat:
            self.last_re = bre(pat)
        if not self.last_re:
            raise EdError('no previous regular expression')
        return self.last_re

    def load(self, name):
        text = self.sh.fs.read(self.sh.path(name))
        if text is None:
            raise EdError(f'cannot open {name}')
        lines = [Line(x) for x in text.split('\n')]
        if lines and lines[-1] == '':
            lines.pop()
        self.w(f'{len(text)}\n')
        return lines

    def snapshot(self):
        if not self.in_g:
            self.undo = (list(self.buf), self.cur)
        self.dirty = True

    def addr(self, s, i):
        n = None
        while i < len(s):
            c = s[i]
            if c in '.$' or c.isdigit() or c in '/?':
                if n is not None:
                    break
                if c == '.':
                    n, i = self.cur, i + 1
                elif c == '$':
                    n, i = len(self.buf), i + 1
                elif c.isdigit():
                    j = i
                    while j < len(s) and s[j].isdigit():
                        j += 1
                    n, i = int(s[i:j]), j
                else:
                    pat, i = delimited(s, i + 1, c)
                    rx = self.regex(pat)
                    N = len(self.buf)
                    order = [(self.cur + k) % N or N for k in range(1, N + 1)] if c == '/' else \
                            [(self.cur - k - 1) % N + 1 for k in range(N)]
                    n = next((k for k in order if rx.search(self.buf[k - 1])), None)
                    if n is None:
                        raise EdError('no match')
            elif c in '+-^':
                j = i + 1
                while j < len(s) and s[j].isdigit():
                    j += 1
                k = int(s[i + 1:j]) if j > i + 1 else 1
                n = (self.cur if n is None else n) + (k if c == '+' else -k)
                i = j
            else:
                break
        return n, i

    def check(self, a, b, zero=False):
        if not (0 if zero else 1) <= a <= b <= len(self.buf) or (b == 0 and not zero):
            raise EdError('address out of range')
        return a, b

    # -- commands
    def command(self, line):
        a1, i = self.addr(line, 0)
        given = 0 if a1 is None else 1
        if i < len(line) and line[i] in ',;':
            sep = line[i]
            if a1 is None:
                a1 = 1 if sep == ',' else self.cur
            if sep == ';':
                self.cur = a1
            a2, i = self.addr(line, i + 1)
            if a2 is None:
                a2 = len(self.buf) if not given else a1
            given = 2
        else:
            a2 = a1
        c, rest = (line[i], line[i + 1:]) if i < len(line) else ('', '')
        dot = self.cur

        def rng(da, db, zero=False):
            return self.check(da if a1 is None else a1, db if a2 is None else a2, zero)

        if c == '':
            n = a2 if given else dot + 1
            self.check(n, n)
            self.w(self.buf[n - 1] + '\n')
            self.cur = n
        elif c in 'pnl':
            lo, hi = rng(dot, dot)
            self.show(lo, hi, c)
        elif c == '=':
            self.w(f'{a2 if given else len(self.buf)}\n')
        elif c in 'aic':
            if c == 'c':
                lo, hi = rng(dot, dot)
            else:
                lo, hi = rng(dot, dot, zero=True)
            text = self.input()
            self.snapshot()
            if c == 'c':
                del self.buf[lo - 1:hi]
                at = lo - 1
            else:
                at = hi if c == 'a' else max(hi - 1, 0)
            self.buf[at:at] = text
            self.cur = at + len(text) if text else (min(at, len(self.buf)) if c == 'c' else at)
        elif c == 'd':
            lo, hi = rng(dot, dot)
            self.snapshot()
            del self.buf[lo - 1:hi]
            self.cur = min(lo, len(self.buf))
        elif c == 's':
            self.substitute(rng(dot, dot), rest)
        elif c in 'gv':
            if self.in_g:
                raise EdError('global inside global')
            lo, hi = rng(1, len(self.buf))
            if not rest:
                raise EdError('missing pattern')
            pat, j = delimited(rest, 1, rest[0])
            rx = self.regex(pat)
            cmdlist = rest[j:] or 'p'
            marked = [ln for ln in self.buf[lo - 1:hi] if bool(rx.search(ln)) == (c == 'g')]
            self.snapshot()
            self.in_g = True
            try:
                for ln in marked:
                    self.tty.check()                # ^C or a hang-up stops a long g//
                    k = next((k for k, x in enumerate(self.buf) if x is ln), None)
                    if k is not None:          # ponytail: O(n^2) identity scan, fine at terminal-sized files
                        self.cur = k + 1
                        self.command(cmdlist)
            finally:
                self.in_g = False
        elif c in 'mt':
            lo, hi = rng(dot, dot)
            dest, _ = self.addr(rest.strip(), 0)
            if dest is None or not 0 <= dest <= len(self.buf) or (c == 'm' and lo <= dest < hi):
                raise EdError('bad destination')
            self.snapshot()
            chunk = [Line(x) for x in self.buf[lo - 1:hi]]
            if c == 'm':
                del self.buf[lo - 1:hi]
                if dest >= hi:
                    dest -= hi - lo + 1
            self.buf[dest:dest] = chunk
            self.cur = dest + len(chunk)
        elif c == 'j':
            lo, hi = rng(dot, dot + 1) if given < 2 else rng(dot, dot)
            if hi > lo:
                self.snapshot()
                self.buf[lo - 1:hi] = [Line(''.join(self.buf[lo - 1:hi]))]
            self.cur = lo
        elif c in 'wW':
            lo, hi = rng(1, len(self.buf), zero=True) if self.buf else (1, 0)
            name = rest.strip() or self.fname
            if not name:
                raise EdError('no file name')
            self.fname = self.fname or name
            text = ''.join(x + '\n' for x in self.buf[lo - 1:hi])
            try:
                if not self.sh.fs.write(self.sh.path(name), text, append=c == 'W'):
                    raise EdError(f'cannot create {name}')
            except NoSpace as e:
                raise EdError(str(e))
            self.w(f'{len(text)}\n')
            if (lo, hi) in ((1, len(self.buf)), (1, 0)):
                self.dirty = False
        elif c == 'r':
            _, hi = rng(len(self.buf), len(self.buf), zero=True)
            name = rest.strip() or self.fname
            if not name:
                raise EdError('no file name')
            lines = self.load(name)
            self.snapshot()
            self.buf[hi:hi] = lines
            self.cur = hi + len(lines)
        elif c in 'eE':
            if c == 'e' and self.dirty and not self.warned:
                self.warned = True
                raise EdError('warning: buffer modified (e again to discard)')
            name = rest.strip() or self.fname
            if not name:
                raise EdError('no file name')
            self.fname = name
            self.buf, self.undo, self.dirty = self.load(name), None, False
            self.cur = len(self.buf)
        elif c == 'f':
            if rest.strip():
                self.fname = rest.strip()
            self.w(self.fname + '\n')
        elif c in 'qQ':
            if c == 'q' and self.dirty and not self.warned:
                self.warned = True
                raise EdError('warning: buffer modified (q again to quit)')
            return 'quit'
        elif c == 'u':
            if not self.undo:
                raise EdError('nothing to undo')
            (self.buf, self.cur), self.undo = self.undo, (list(self.buf), self.cur)
        elif c == 'h':
            self.w(self.err + '\n')
        elif c == '!':
            self.sh.run_line(rest)
            self.w('!\n')
        else:
            raise EdError(f'unknown command "{c}"')

    def show(self, lo, hi, c):
        for k in range(lo, hi + 1):
            text = self.buf[k - 1]
            if c == 'l':
                text = text.replace('\\', '\\\\').replace('\t', '\\t').replace('\b', '\\b')
            self.w((f'{k}\t' if c == 'n' else '') + text + '\n')
        self.cur = hi

    def input(self):
        lines = []
        while True:
            try:
                x = self.tty.readline()
            except EOF:
                break
            if x == '.':
                break
            lines.append(Line(x))
        return lines

    def substitute(self, lohi, rest):
        lo, hi = lohi
        if not rest or rest[0] in ' \n':
            raise EdError('bad substitute')
        d = rest[0]
        pat, j = delimited(rest, 1, d)
        rep, j = delimited(rest, j, d)
        flags = rest[j:]
        if set(flags) - set('gpnl'):
            raise EdError('bad flags')
        rx = self.regex(pat)
        f, changed = subst(rep), None
        for k in range(lo, hi + 1):
            new, n = rx.subn(f, self.buf[k - 1], count=0 if 'g' in flags else 1)
            if n:
                if changed is None:
                    self.snapshot()
                self.buf[k - 1] = Line(new)
                changed = k
        if changed is None:
            if self.in_g:
                return
            raise EdError('no match')
        self.cur = changed
        if set(flags) & set('pnl'):
            self.show(changed, changed, 'n' if 'n' in flags else 'l' if 'l' in flags else 'p')


def session(tty):
    """getty + login forever: log out and the login prompt comes back."""
    fs = FS()
    seed(fs)
    tty.write(BOOT)
    while True:
        try:
            tty.write('login: ')
            user = tty.readline().strip()
        except (Interrupt, EOF):
            continue
        if not user:
            continue
        if not re.fullmatch(r'[a-z][a-z0-9]{0,7}', user):
            tty.write('Login incorrect\n')
            continue
        sh = Shell(tty, fs, user)
        fs.mkdir(sh.home)
        seed_home(fs, sh.home)
        tty.write(fs.read('/etc/motd'))
        sh.run()
        tty.write('\n')

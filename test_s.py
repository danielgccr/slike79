"""S checks against the manual's own examples. Run: uv run python test_s.py"""
import s


class FakeTty:
    def __init__(self, lines=()):
        self.lines, self.out = list(lines), []

    def write(self, text):
        self.out.append(text)

    def check(self):
        pass

    def readline(self):
        if not self.lines:
            raise s.EOF
        return self.lines.pop(0)


def session(*lines):
    t = FakeTty(lines)
    s.Interp(t).repl()
    return ''.join(t.out)


def run(src):
    t = FakeTty()
    s.Interp(t).run(src)
    return ''.join(t.out)


# 1981 "syntax" page: command form with arguments, and a bare name is a function before a dataset
assert run('x <- 1:5; mean x; print x, 7') == ' 3\n 1 2 3 4 5\n 7\n'
assert 'Error: dataset "man" not found' in session('man')
assert 'argument "x" is missing' in session('mean <- 1:3', 'mean')
assert 'mean(x, trim=)' in run('help mean')

# printing, verbatim shapes from manual section 2
assert run('c(1:3, 5, 7, 9)') == ' 1 2 3 5 7 9\n'
assert run('rep(1:3,2)') == ' 1 2 3 1 2 3\n'
assert run('x <- c(1,-1,2,-2,.5); sort(x)') == ' -2.0 -1.0  0.5  1.0  2.0\n'
assert run('x <- c(1,-1,2,-2,.5); order(x)') == ' 4 2 5 1 3\n'
assert run('Month.length > 30') == ' T F T F T F T T F T F T\n'
assert run('matrix(1:12, 3, 4)') == ('Array:\n3 by 4\n      [,1]  [,2]  [,3]  [,4]\n'
                                     '[1,]     1     4     7    10\n[2,]     2     5     8    11\n'
                                     '[3,]     3     6     9    12\n')
long = run('1:30').splitlines()
assert long[1].startswith('[') and len(long) == 2, long

# language
assert run('x_3; x') == ' 3\n'                       # underline assignment
assert run('3 -> y; y') == ' 3\n'
assert run('-2^2; -1:2') == ' -4\n -1  0  1  2\n'
assert run('7 %/ 2; 7 %% 2; 7/2') == ' 3\n 1\n 3.5\n'
assert run('y <- 0; for (i in 1:10) y <- y + i; y') == ' 55\n'
assert run('x <- c(1,-1,2); x[x<0] <- 0; x') == ' 1 0 2\n'
assert run('x <- 1:5; x[-1]; x[c(T,F)]') == ' 2 3 4 5\n 1 3 5\n'
assert run('m <- matrix(1:6,2); m[,2]; m[2,]') == ' 3 4\n 2 4 6\n'
assert run('mean(c(1,2,3,100), trim=.25)') == ' 2.5\n'     # prefix-free named arg
assert run('mean(c(1,2,3,100), tr=.25)') == ' 2.5\n'       # unique prefix match
assert run('NA(c(1,NA,3))') == ' F T F\n'

# errors and continuation, as in the manual
out = session('x+7,5 # I meant 7.5')
assert 'Syntax error\nx+7,5 # I meant 7.5\n   ^\n' in out, out
out = session('1+"abc"')
assert 'Error: attempt to use character data in arithmetic\nError in +\n' in out, out
out = session('z <- 1 + (2 *', '3)', 'z')
assert '+ ' in out and ' 7\n' in out, out
assert session('q', '1').count('> ') == 1                 # bare q quits

# graphics: printer frame has the dot border and every point
pic = run('plot(1:10); show')
assert pic.count('*') == 10 and '.....' in pic, pic
assert '\x1b]1979;E;<svg' in run('tek14; plot(1:3)')
stem = run('stem(state.x77[1:10,2])')
assert 'N =  10   Median =  4812.000   Hinges =  4091.000 5114.000' in stem
assert '     2      2    3 : 46' in stem and '            5    4 : 15889' in stem, stem

# limits stop runaway sessions
assert 'too long' in session('1:1e9')
# lowess and approx agree with R, whose lowess is Cleveland's reference code; structures and $
fit = run('l <- lowess(state.x77[1:20,2], state.x77[1:20,4]); l$y')
assert fit.split()[:4] == ['69.60508', '69.75313', '69.82810', '69.89628'] and '69.42359' in fit, fit
assert run('lowess(c(1,2,2,3,4,5,9,10), c(2,1,4,3,8,5,9,7), f=.5, iter=0, delta=2)') == \
    'x:\n  1  2  3  4  5  9 10\ny:\n 2.000000 2.500000 3.000000 4.479089 5.958178 7.799881 7.877133\n'
assert run('approx(c(1,2,3), c(10,20,30), c(1.5,2.5,4))$y; approx(1:3, c(10,20,30), c(0,4), rule=2)$y') == \
    ' 15 25 NA\n 10 30\n'
assert run('z <- approx(1:3, 1:3, 2); ncomp(z); z$[2]; matrix(1:6,2)$Dim; z$x') == ' 2\n 2\n 2 3\n 2\n'
assert 'select a component with $' in session('y <- 1:3; y - approx(1:3, 1:3, 1:3)')
assert 'ambiguous' in session('matrix(1:6,2)$D')
resid = run('x <- state.x77[,2]; y <- state.x77[,4]; fit <- lowess(x,y); r <- y-approx(fit,x)$y; len(r); max(abs(r)) < 3')
assert resid == ' 50\n T\n', resid
pic = run('x <- state.x77[,2]; y <- state.x77[,4]; plot(x, y); lines(lowess(x, y)); show')
assert pic.count('*') >= 45 and ('-' in pic or '/' in pic), pic

# the macro processor (manual section 4): text substitution before parsing
import smacro
assert run('x <- c(5, 1, 7, 2); ?which(x > 3); list') == ' 1 3\n "x"\n'      # temporaries removed
assert 'MACRO sample(x,n/?PROMPT(Sample size:)/)\n(?rperm($1)[seq($2)])\nEND' in run('mprint(mac.sample)')
assert len([w for w in session('?sample(1:10)', '3').split('Sample size: ')[1].split() if w.isdigit()]) == 3
e = smacro.Expander(s.Interp(FakeTty()))
assert e.expand('?IFELSE(a, a, yes, no)?IFELSE(T, TRUE, yes, no)') == 'yesno'        # strings, not values
assert e.expand('?LOOP(f($%1),x,y)|?SUBSTR(hello,2,3)|?(?kept)|?DEFINE(sq,$1*$1)?sq(3)') == 'f(x),f(y)|ell|?kept|3*3'
I = s.Interp(FakeTty())
I.db[1].update(smacro.compile_macros("""MACRO t(y, by/2/, opt=/o/)
c(y, by, "opt", $*)
END"""))
assert I.db[1]['mac.t'].v[1] == 'c($1, $2, "$3", $*)'                              # names rewritten, even in strings
assert smacro.expand(I, '?t(a)') == 'c(a, 2, "o", )' and smacro.expand(I, '?t(a, b, c, opt=z)') == 'c(a, b, "z", c)'
assert smacro.expand(I, '?t(m[,1], f(u, v))') == 'c(m[,1], f(u, v), "o", )'        # brackets and parens
assert 'Error: no x' in session('?FATAL(no x)') and 'not defined' in session('?nosuch(1)')
assert run('x <- 1:3; rm(x, value=x * 2); list') == ' 2 4 6\nNULL\n'               # value= before removal

# the documentation: every function in one topic, with an example that runs
import sdoc
grouped = [n for _, _, names in sdoc.TOPICS for n in names.split()]
assert sorted(grouped) == sorted(s.BUILTINS) and len(grouped) == len(set(grouped)), set(s.BUILTINS) ^ set(grouped)
assert set(sdoc.EXAMPLES) == set(s.BUILTINS)
for name, ex in sdoc.EXAMPLES.items():
    if name not in sdoc.NO_RUN:
        assert 'Error' not in sdoc.run_example(ex), (name, sdoc.run_example(ex))
page = run('help(mean)')
assert 'mean(x, trim=)' in page and 'trim=.1)' in page and ' 4430.075' in page and 'See also' in page, page
everything = sdoc.manual() + sdoc.help_index() + ''.join(sdoc.help_page(n) for n in s.BUILTINS)
assert all(len(line) <= 80 for line in everything.split('\n')), \
    [line for line in everything.split('\n') if len(line) > 80]
print('test_s: ok')

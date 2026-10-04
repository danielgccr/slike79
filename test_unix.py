"""ed and sh checks: scripted sessions on the in-memory file system. Run: uv run python test_unix.py"""
import re

import unix
from test_s import FakeTty


def ed(*lines, files=None):
    t = FakeTty(lines)
    fs = unix.FS()
    unix.seed(fs)
    fs.mkdir('/usr/dmr')
    for k, v in (files or {}).items():
        fs.write(k, v)
    sh = unix.Shell(t, fs, 'dmr')
    sh.run_line('ed' + (' f' if files else ''))
    return ''.join(t.out), fs


out, fs = ed('a', 'hello world', 'second line', '.', 'w f', 'q')
assert fs.read('/usr/dmr/f') == 'hello world\nsecond line\n'
assert out.endswith('24\n'), out

out, fs = ed('1,$s/o/0/g', ',p', 'w', 'q', files={'/usr/dmr/f': 'foo\nbar\nboo\n'})
assert out == '12\nf00\nbar\nb00\n12\n', out

out, fs = ed('g/oo/d', ',n', 'q', 'q', files={'/usr/dmr/f': 'foo\nbar\nboo\n'})
assert out == '12\n1\tbar\n?\n', out              # first q warns: buffer modified

out, fs = ed(r's/\(f\)\(o*\)/\2\1/p', 'u', 'p', 'Q', files={'/usr/dmr/f': 'foo\n'})
assert out == '4\noof\nfoo\n', out

out, fs = ed('/b/', '?f?', '$=', '2m0', ',p', 'Q', files={'/usr/dmr/f': 'foo\nbar\nbaz\n'})
assert out == '12\nbar\nfoo\n3\nbar\nfoo\nbaz\n', out

out, fs = ed('7p', 'h', 'Q', files={'/usr/dmr/f': 'x\n'})
assert out == '2\n?\naddress out of range\n', out


# the 1982 film: Kernighan's spelling checker, as a pipeline and as a shell procedure
def sh(*lines):
    t = FakeTty(lines)
    fs = unix.FS()
    unix.seed(fs)
    fs.mkdir('/usr/bwk')
    unix.seed_home(fs, '/usr/bwk')
    unix.Shell(t, fs, 'bwk').run()
    return ''.join(t.out), fs


spell = "tr -cs A-Za-z '\\012' < $1 | sort | uniq | comm -23 - dictionary"
out, fs = sh(spell.replace('$1', 'document'))
assert out == '$ conect\nwritting\n$ ', out
out, fs = sh('ed spell', 'a', spell, '.', 'w', 'q', 'spell document', 'chmod +x spell', 'spell document > typos')
assert 'spell: cannot execute' in out and fs.read('/usr/bwk/typos') == 'conect\nwritting\n', out
out, _ = sh('echo b a b | tr " " "\\012" | sort | uniq -c', 'comm -12 document document | wc')
assert '   1 a\n   2 b\n' in out and '      4' in out, out

# Cherry's eqn | troff: eqn writes troff motions, troff sends a page proof
out, _ = sh('eqn equations | troff')
assert out.count('\x1b]1980;<svg') == 1 and '√' in out and 'Σ' in out, out[:200]
assert "\\v'" in sh('eqn equations')[0]
# period fidelity: V7 tr has no \n, and ^ is a pipe to sh
out, _ = sh("echo a b | tr ' ' '\\n'", 'echo hi ^ tr a-z A-Z')
assert '$ anb\n' in out and '$ HI\n' in out, out

# the line discipline is the only layer that knows how a line was typed
import vt


def tty(mode, typed):
    sent = []
    t = vt.Tty(sent.append)
    t.set_mode(mode)
    t.feed(typed)
    return t, sent


t, sent = tty('1979', 'echo ab#c\r' 'x@y\r' 'a\\#b\r' '\x7f')
assert [t.readline(), t.readline(), t.readline()] == ['echo ac', 'y', 'a#b']
assert ''.join(sent).startswith('echo ab#c\r\nx@\r\ny'), sent        # nothing rubbed out, @ ends the line
try:
    t.readline()
    raise AssertionError('DEL must interrupt')
except vt.Interrupt:
    pass

t, sent = tty('modern', 'ab\x7fc\r' '\x1b[A\r')
t.write('> ')
assert t.readline() == 'ac'
t.write('> ')
assert t.readline() == 'ac'                  # history kept per prompt, without the program asking

t, sent = tty('1979', "stty erase '^h'\r" 'echo ab\x08c\r' 'echo a#b\r' '\x04')
fs = unix.FS()
unix.seed(fs)
unix.Shell(t, fs, 'bwk').run()
screen = ''.join(sent)
assert '\r\nac\r\n' in screen and '\r\na#b\r\n' in screen, screen   # ^H erases now, # is a character
# clear empties the scrollback too, and its escapes never become part of the prompt
t, sent = tty('modern', 'clear\r' 'ab\x7f\r' '\x04')
fs = unix.FS()
unix.seed(fs)
unix.Shell(t, fs, 'bwk').run()
screen = ''.join(sent)
assert '\x1b[H\x1b[2J\x1b[3J' in screen and screen.count('\x1b[2J') == 1, screen   # Backspace redraw did not clear again
# the backfitting macro, as a 1981 user would run it; numbers checked against R with delta=0
t, sent = tty('modern', 'S\r' 'define("backfit")\r'
              'fitted <- ?backfit(state.x77[,4], state.x77[,5], state.x77[,2])\r'
              'list\r' 'round(fitted[1:3], 4); round(var(state.x77[,4] - fitted), 6)\r' 'q\r' '\x04')
fs = unix.FS()
unix.seed(fs)
fs.mkdir('/usr/th')
unix.seed_home(fs, '/usr/th')
unix.Shell(t, fs, 'th').run()
screen = ''.join(sent).replace('\r\n', '\n')
assert 'mac.backfit\n' in screen and '"f1"     "f2" "fitted"' in screen, screen
assert ' 68.5227 69.4257 70.7936\n 0.591581\n' in screen, screen
import smacro
assert all(len(line) <= 80 for line in smacro.MANUAL.split('\n'))
# the worked examples run cleanly, and the page carries their output and pictures
import sexamples
for title, _, lines, _, *where in sexamples.EXAMPLES:
    steps, _, _ = sexamples.run(lines, *where)
    assert not any('Error' in out or 'not found' in out or "can't" in out for _, out in steps), (title, steps)
    assert not any('#' in line or '?' in line for line in lines), title   # safe to type in 1979 mode
page = sexamples.page()
assert page.count('class="type-it"') == len(sexamples.EXAMPLES) and page.count('<figure') == 4
assert '<b>' in page and 'Figure 1: paste up the Tektronix plot here' in page
assert '0.3402553' in page and 'Read 40 items' in page
# reports: neqn draws in characters, nroff -ms formats, spp runs S and fills in strings
import typeset
assert typeset.AsciiEqn('s sup 2 = 1 over {n - 1}').seq(10).lines == [' 2      1   ', 's  = -------', '      n - 1 ']
plain = lambda text: re.sub('.\b', '', text)
t, sent = tty('modern', 'spp report | neqn | nroff -ms | col -b\r' 'S < analysis > results\r' 'nroff -ms memo\r'
              'spp report | eqn | troff -ms\r' '\x04')
fs = unix.FS()
unix.seed(fs)
fs.mkdir('/usr/rab')
unix.seed_home(fs, '/usr/rab')
unix.Shell(t, fs, 'rab').run()
screen = plain(''.join(sent).replace('\r\n', '\n'))
assert 'ranged from 67.96 to 73.6 years,' in screen and 'correlation is only 0.34' in screen, screen
assert '1.  The data' in screen and 'ABSTRACT' in screen and '\\--' in screen and 'Figure 1: paste up' in screen
assert '      70.8786' in screen and '\x1b]1980;<svg' in screen                 # .so results, and the proof
assert all(len(line) <= 80 for line in unix.MANPAGES['spp'].split('\n'))
# guards for a public machine: line length, disk, output, datasets, time
t, sent = tty('modern', 'x' * 5000 + '\r')
assert len(t.readline()) == 4096 and sent.count('\x07') == 904
t, sent = tty('1979', 'y' * 300 + '\r')
assert len(t.readline()) == 256                                          # V7's CANBSIZ
out, fs = sh('echo hello > a', 'cat a a a a a a a a > b', 'cat b b b b b b b b > a', 'cat a a a a a a a a > b',
             'cat b b b b b b b b > a', 'cat a a a a a a a a > b', 'cat b b b b b b b b > a', 'cat a a a a a a a a > b')
assert 'b: No space left on device' in out and sum(map(len, fs.files.values())) <= unix.FS_LIMIT, out
big = FakeTty(['cat a a a a a a'])
fs = unix.FS()
unix.seed(fs)
fs.mkdir('/usr/bwk')
fs.files['/usr/bwk/a'] = 'z' * 1_000_000
unix.Shell(big, fs, 'bwk').run()
assert 'cat: output stopped at 4 MB' in ''.join(big.out)
assert sum(len(x) for x in big.out if x.startswith('z')) <= unix.OUTPUT_LIMIT
budget = sh('S', 'a <- runif(100000); b <- a; c <- a; d <- a; e <- a; f <- a', 'list', 'q')[0]
assert 'limit here: rm some first' in budget and '"f"' not in budget, budget
import s as S_
S_.TIME_LIMIT = 1
slow = sh('S', 'i <- 0; repeat i <- i + 1', 'q')[0]
S_.TIME_LIMIT = 30
assert 'stopped after 1 seconds' in slow, slow
# every login, root included, finds the example files at home; a second login keeps your edits
t, sent = tty('modern', 'root\r' 'S\r' 'm <- matrix(read("mydata"), ncol=4, byrow=T)\r' 'q\r'
              'echo mine > mydata\r' '\x04' 'root\r' 'cat mydata\r' '\x04')
t.q.put(None)                     # then the line hangs up, ending the login loop
try:
    unix.session(t)
except vt.Hangup:
    pass
screen = ''.join(sent).replace('\r\n', '\n')
assert 'Read 40 items' in screen and '# cat mydata\nmine\n' in screen, screen[-400:]
print('test_unix: ok')

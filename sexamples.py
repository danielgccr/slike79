"""Worked examples for the page: a first statistical analysis in S, step by step.

Every transcript is produced by running the lines through this S, so the page shows
exactly what the terminal prints; Tektronix pictures are kept as images.
"""
import html
import json
import re
from urllib.parse import quote

import s
import unix

OSC = re.compile(r'\x1b\]1979;(?:E;)?([^\x07]*)\x07')
PROOF = re.compile(r'\x1b\]1980;([^\x07]*)\x07')

EXAMPLES = [
    ('A summary of every column',
     'state.x77 holds figures for the 50 states, one column per variable. A loop fills a matrix '
     'with the smallest value, the median and the largest of each column; print labels it.',
     ['state.vars',
      'summ <- matrix(0, 8, 3)',
      'for (j in 1:8) summ[j,] <- c(min(state.x77[,j]), median(state.x77[,j]), max(state.x77[,j]))',
      'print(summ, rowlab=state.vars, collab=c("min", "median", "max"))'],
     'Inside the loop nothing prints by itself; print shows the finished table.'),

    ('One variable, closely',
     'Pull out a column, then ask for its size, centre and spread.',
     ['income <- state.x77[,2]',
      'len(income); range(income)',
      'mean(income); median(income)',
      'sqrt(var(income))',
      'mean(income, trim=.1)',
      'stem(income)'],
     'When the trimmed mean stays close to the plain mean, no handful of states is pulling it. '
     'The stem-and-leaf display keeps the digits: stems are thousands of dollars, leaves hundreds.'),

    ('The states at the extremes',
     'order gives the subscripts that sort a vector, so it can sort one vector by another.',
     ['income <- state.x77[,2]',
      'state.name[order(income)][1:3]',
      'state.name[order(-income)][1:3]',
      'state.abb[income > 5000]',
      'sum(income > 5000)'],
     'income > 5000 is a logical vector: as a subscript it picks those states, and sum counts them.'),

    ('The shape of a distribution',
     'On the line printer, a plot is kept until show, or until the next plot starts.',
     ['income <- state.x77[,2]',
      'printer',
      'hist(income, main="Per capita income, 1977")',
      'show',
      'boxplot(income, main="Per capita income, 1977")',
      'show'],
     'The box runs from the lower to the upper hinge with the median across it.'),

    ('Two variables: a scatter plot and a smooth',
     'On the Tektronix 4014, lines adds Cleveland\'s lowess smooth to the scatter plot. The '
     'correlation is just arithmetic on whole vectors.',
     ['income <- state.x77[,2]; life <- state.x77[,4]',
      'tek14',
      'plot(income, life, xlab="Income", ylab="Life expectancy")',
      'lines(lowess(income, life))',
      'dx <- income - mean(income); dy <- life - mean(life)',
      'sum(dx * dy) / sqrt(sum(dx^2) * sum(dy^2))'],
     'The smooth rises with income and then levels off; one rich, outlying state pulls its right end '
     'down. A correlation of about a third says income alone explains little of life expectancy.'),

    ('A straight line by least squares',
     'regress is not on this machine yet, but the slope and intercept are two lines of arithmetic. '
     'The residuals then show which states the line fits worst.',
     ['life <- state.x77[,4]; murder <- state.x77[,5]',
      'dx <- murder - mean(murder)',
      'b <- sum(dx * (life - mean(life))) / sum(dx^2)',
      'a <- mean(life) - b * mean(murder)',
      'a; b',
      'resid <- life - (a + b * murder)',
      'state.name[order(resid)][1:3]',
      'state.name[order(-resid)][1:3]',
      'tek14',
      'plot(murder, life, xlab="Murder rate", ylab="Life expectancy")',
      'abline(a, b)'],
     'Each extra murder per 100,000 people goes with about 0.28 of a year, some three and a half '
     'months, less life expectancy. The first '
     'three states live shorter lives than their murder rate predicts, the last three longer.'),

    ('Comparing groups',
     'A logical subscript splits the data into groups: here, states with more or less than '
     '1.5 per cent illiteracy.',
     ['illit <- state.x77[,3]; life <- state.x77[,4]',
      'sum(illit > 1.5)',
      'mean(life[illit > 1.5]); mean(life[illit <= 1.5])',
      'median(life[illit > 1.5]); median(life[illit <= 1.5])'],
     'Mean and median tell the same story, so the gap is not the work of a few unusual states.'),

    ('A report, the 1981 way',
     'At the shell prompt ($), not inside S. Reports in 1981 took two steps: run S on its own with '
     'its output in a file, then format a document that reads the file with troff\'s .so request. '
     'nroff -ms prints the draft on the terminal; troff -ms sets the page.',
     ['cat analysis',
      'S < analysis > results',
      'nroff -ms memo',
      'troff -ms memo'],
     'Run S again and format again, and the listing follows the data. Numbers inside the sentences '
     'still had to be copied by hand.', 'sh'),

    ('A report as it could have been: spp',
     'At the shell prompt ($). A what if: spp is a troff preprocessor, like eqn, that runs the S '
     'lines between .SS and .SE and puts each listing with its output in its place, and turns '
     '.SR mn mean(life) into a troff string \\*(mn for the text. man spp tells the story.',
     ['spp report | neqn | nroff -ms | col',
      'spp report | eqn | troff -ms'],
     'Every piece existed in 1981: pipes, troff preprocessors, the -ms macros, S reading from a file. '
     'Nobody joined them until Sweave in 2002. A Tektronix plot could not go into troff output, so '
     'spp leaves a box to paste it into, as authors did.', 'sh'),

    ('Your own data, from a file',
     'Your home directory has a file mydata: four numbers to a line for ten states (population, '
     'income, illiteracy, life expectancy). read takes it in as one vector; matrix gives it shape.',
     ['m <- matrix(read("mydata"), ncol=4, byrow=T)',
      'm',
      'for (j in 1:4) print(mean(m[,j]))'],
     'This is the manual\'s own example session. To use other data, write a file with ed and read it '
     'the same way.'),
]


class _Capture:
    def __init__(self):
        self.out = []

    def write(self, text):
        self.out.append(text)

    def check(self):
        pass

    def readline(self):
        raise s.EOF


def run(lines, where='S'):
    """[(command, output text)], the last Tektronix picture and the last troff proof, from a fresh
    machine with a home directory: lines go to S, or to the shell when where is 'sh'."""
    io = _Capture()
    fs = unix.FS()
    unix.seed(fs)
    fs.mkdir('/usr/guest')
    unix.seed_home(fs, '/usr/guest')
    shell = unix.Shell(io, fs, 'guest')
    interp = s.Interp(io, shell)
    steps, picture, proof = [], None, None
    for line in lines:
        io.out = []
        try:
            shell.run_line(line) if where == 'sh' else interp.run(line)
        except s.SError as e:
            io.out.append(f'Error: {e}\n' + (f'Error in {e.where}\n' if e.where else ''))
        text = ''.join(io.out)
        picture = (OSC.findall(text) or [picture])[-1]
        proof = (PROOF.findall(text) or [proof])[-1]
        steps.append((line, PROOF.sub('', OSC.sub('', text))))
    return steps, picture, proof


def overstrikes(escaped):
    """nroff's c-backspace-c is bold and _-backspace-c is underlined: show them as such."""
    escaped = re.sub(r'_\x08([^\x08])', r'<u>\1</u>', escaped)
    return re.sub(r'([^\x08])\x08\1', r'<b>\1</b>', escaped).replace('</b><b>', '').replace('</u><u>', '')


def page():
    e = html.escape
    out = ['<header><h2>Worked examples</h2><p>A first statistical analysis with the 1977 state '
           'data, then a report. Start S in the terminal (type <code>S</code>), then press '
           '<em>Type it</em> to enter an example, or type the lines yourself; the two report '
           'examples go at the shell prompt instead. Each transcript below was produced by this '
           'machine.</p></header>']
    for title, intro, lines, after, *where in EXAMPLES:
        where = where[0] if where else 'S'
        steps, picture, proof = run(lines, where)
        prompt = '$' if where == 'sh' else '&gt;'
        session = ''.join(f'{prompt} {e(cmd)}\n{overstrikes(e(text))}' for cmd, text in steps)
        out.append(f'<section><h3>{e(title)}</h3><p>{e(intro)}</p>'
                   f'<button type="button" class="type-it" data-type="{e(json.dumps(lines))}">Type it</button>'
                   f'<pre class="session">{session}</pre>')
        if picture:
            src = 'data:image/svg+xml;charset=utf-8,' + quote(picture, safe='')
            out.append(f'<figure class="tek-shot"><img src="{src}" alt="{e(title)}, on the Tektronix 4014">'
                       '<figcaption>The Tektronix 4014 afterwards</figcaption></figure>')
        if proof:
            src = 'data:image/svg+xml;charset=utf-8,' + quote(proof, safe='')
            out.append(f'<figure class="proof-shot"><img src="{src}" alt="{e(title)}: the typeset page">'
                       '<figcaption>The phototypesetter proof from troff -ms</figcaption></figure>')
        out.append(f'<p>{e(after)}</p></section>')
    return ''.join(out)


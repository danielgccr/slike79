"""S documentation: the manual page (man S) and the online help (help(name)).

The explanations follow Becker & Chambers' 1981 manual and Richard A. Becker,
"A Brief History of S" (AT&T Bell Laboratories). As the paper says S had from the
start, every function has its own documentation: usage, defaults, details, an example
and cross references. Examples are run when help is asked for, so the output shown
is always what this S really prints.
"""
import textwrap

import s

HISTORY = 'https://sas.uwaterloo.ca/~rwoldfor/software/R-code/historyOfS.pdf'

TOPICS = [
    ('Combining and sequences',
     'Data in S are vectors: values of one kind (numbers, strings or logical values) under one name. '
     'c builds a vector from pieces; the operator : and seq build sequences.',
     'c seq rep'),
    ('Arithmetic',
     'These work on every element of a vector at once, the implicit looping that lets most analyses '
     'do without loops. Operators do the same: x + 1 adds 1 to each element, and when two vectors of '
     'different lengths meet, the shorter one is reused.',
     'abs sqrt exp log log10 sin cos asin acos atan ceiling floor trunc round'),
    ('Summaries',
     'Each reduces data to a few numbers. NA in the data is an error: remove missing values first.',
     'sum prod max min range mean median var cumsum diff'),
    ('Sorting and matching',
     'Most return subscripts rather than values, ready to use inside [ ].',
     'sort order rank rev match unique all any'),
    ('Attributes and missing values',
     'What kind of data a vector holds, how long it is, and where values are missing.',
     'len mode NA'),
    ('Matrices',
     'A matrix is a vector structure: an ordinary vector, stored column by column, '
     'with a Dim vector of rows and columns carried along with it.',
     'matrix nrow ncol t row col cbind rbind'),
    ('Smoothing and structures',
     'lowess, the scatter plot smoother W. S. Cleveland of Bell Laboratories published in 1979, and '
     'approx return a structure with components x and y: a graphical data structure, which plot, '
     'points and lines take in place of x and y. $ selects a component, by name or by number.',
     'lowess approx ncomp'),
    ('Macros',
     'A macro is text that S substitutes for ?name(args) before it parses the line; man macro '
     'explains how to write them. The shared directory holds the manual\'s which, rperm and sample.',
     'define mprint medit'),
    ('Random numbers',
     'Samples from distributions, for simulations and for trying out methods.',
     'rnorm runif'),
    ('Datasets',
     'Assignment stores a dataset on the working directory; S searches working, save and shared in turn.',
     'list rm save get assign'),
    ('Input, output and help',
     'S reads raw data in, computes on it, and prints results; input and output were kept simple '
     'on purpose.',
     'read print help q'),
    ('Graphics',
     'Choose a device, then draw. plot, hist, barplot and boxplot start a new picture; '
     'points, lines, abline, text and title add to the current one.',
     'printer tek14 show par plot hist barplot boxplot stem points lines abline text title'),
]

DETAILS = {
    'c': 'The values are combined in order. The result takes the most general mode among the '
         'arguments (logical, then integer, then real, then character), so c(1, "a") is character. '
         'A matrix given to c loses its Dim and becomes a plain vector.',
    'seq': 'With one number n, seq gives 1, 2, ..., n; with a longer vector x, 1:len(x). seq(from, to) '
           'is the same as from:to. by= sets the step, which must lead from from toward to.',
    'rep': 'With one count, the whole vector is repeated. With one count per element, each element '
           'is repeated its own number of times.',
    'len': 'The number of elements. For a matrix this is nrow times ncol.',
    'mode': 'Arithmetic needs logical, integer or real data. Character data in arithmetic is an error.',
    'NA': 'NA marks a missing value. Arithmetic and comparisons with NA give NA, and most summary '
          'functions refuse data that contain NA, so drop them first with x[!NA(x)].',
    'sum': 'Adds every value of every argument. Logical values count as 0 and 1, so sum(x > 0) '
           'counts the positive values of x.',
    'max': 'The largest value over all the arguments. Character data are compared alphabetically.',
    'min': 'The smallest value over all the arguments. Character data are compared alphabetically.',
    'mean': 'trim=.1 sorts the data and drops the lowest and highest tenth before averaging: a mean '
            'that a few wild values cannot pull away, in the spirit of the exploratory data analysis '
            'that shaped the statistics research at Bell Laboratories.',
    'median': 'The middle value, or the average of the two middle values when there is an even number.',
    'var': 'The sample variance, dividing by n - 1.',
    'diff': 'Differences between each value and the one lag= places before it (1 by default). '
            'The result is lag= values shorter than x.',
    'sort': 'Missing values are dropped. To sort one vector by the values of another, use order.',
    'order': 'order(x) gives the subscripts that would sort x, so x[order(x)] is sorted. With more '
             'arguments, ties in the first are broken by the second, and so on. Use it to put one '
             'vector in the order of another: state.name[order(state.x77[,2])].',
    'rank': 'Tied values share the average of the ranks they cover.',
    'match': 'For each value of x, its position in table, or NA when it is not there.',
    'unique': 'The first occurrence of each value is kept, in the original order.',
    'all': 'With NA among the values, the answer is NA unless some value is F.',
    'any': 'With NA among the values, the answer is NA unless some value is T.',
    'round': 'digits= may be negative: round(1234, -2) rounds to hundreds.',
    'matrix': 'The data fill the first column, then the second, and so on; byrow=T fills row by row. '
              'Give nrow= or ncol=: the other is worked out from the length of the data, and data '
              'that are too short are reused.',
    't': 'Rows become columns. A vector is treated as a matrix of one column.',
    'row': 'With col, picks out parts of a matrix by position: m[row(m) >= col(m)] is the lower '
           'triangle.',
    'col': 'With row, picks out parts of a matrix by position: m[row(m) == col(m)] is the diagonal.',
    'cbind': 'Vectors become columns and matrices keep theirs. A vector shorter than the others is '
             'reused, so cbind(1, x) puts a column of ones beside x.',
    'rbind': 'Vectors become rows and matrices keep theirs; short vectors are reused.',
    'rnorm': 'mean= and sd= default to 0 and 1. Each call gives new numbers.',
    'runif': 'min= and max= default to 0 and 1. Each call gives new numbers.',
    'list': 'Typed alone, as a command, list shows the working directory. pos=2 is the save '
            'directory and pos=3 the datasets shared by everyone, such as state.x77.',
    'rm': 'rm(x, y) removes datasets from the working directory, or from the directory pos=; '
          'list= gives names as character strings. value= is evaluated before anything is removed '
          'and returned, so a macro can remove its temporary datasets and still give its result: '
          'rm(list="$Tx", value=$Tx[1]).',
    'save': 'save(x) copies the dataset x to the save directory, where data worth keeping belong. '
            'save(newx=sqrt(x)) stores a computed value under a new name. The working directory '
            'was meant to be cleared out now and then; the save directory was not.',
    'get': 'Takes the name as a character string, so the name itself can be computed.',
    'assign': 'The same as name <- value, with the name given as a character string.',
    'read': 'read("file") reads values separated by blanks or newlines from a file in the shell\'s '
            'current directory. read() reads from the terminal, prompting with the number of the '
            'next item, until an empty line. If the first item is not a number, all items are read '
            'as character strings. len= limits the number of items (2000 by default).',
    'print': 'At top level S prints every value for you; inside braces and loops it does not, and '
             'print does it. rowlab= and collab= label the rows and columns of a matrix. A structure '
             'prints each component under its name.',
    'define': 'Reads MACRO name(arguments) ... END definitions from a file in the shell\'s current '
              'directory, or from the terminal, prompting N> for the MACRO line and D> for the '
              'rest. Each is stored as the dataset mac.name, on the save directory unless pos=1. In '
              'the stored text the argument names become $1, $2, ... . man macro tells the rest.',
    'mprint': 'The text as define stored it: argument names in the body have become $1, $2, ...',
    'medit': 'Opens the definition in ed. Write it and quit, and it is defined again; change the '
             'name on the MACRO line to make a new macro and keep the old one.',
    'lowess': 'For each x, a straight line is fitted by weighted least squares to the fraction f= '
              'of the data nearest to it, the nearest points weighing most, and its value there is '
              'the smooth. The fit is then repeated iter= times with points far from the curve '
              'weighted down, so that a few wild values cannot drag it away: the robust part. With '
              'delta= above 0, x values within delta of the last one fitted are interpolated '
              'instead, to save time. The result is sorted by x, with duplicate x values removed. '
              'The 1981 manual warns that it may be slow for many points: the time grows like '
              'iter*f*n^2. Ctrl-C interrupts it. W. S. Cleveland, "Robust Locally Weighted '
              'Regression and Smoothing Scatterplots", JASA 74 (1979), 829-836.',
    'approx': 'The points (x, y), or one structure with components x and y, are joined by straight '
              'lines and read off at xout=, or at n= evenly spaced points (50 by default). rule=1 '
              'gives NA outside the range of x, rule=2 the value at the nearer end. Points with the '
              'same x are averaged. The 1981 manual\'s lowess example writes resid <- '
              'y-approx(fit,x), but approx returns a structure: take its y component, '
              'y - approx(fit, x)$y.',
    'ncomp': 'With $[i] it steps through the components of a structure: for (i in 1:ncomp(z)) '
             'print(z$[i]). A matrix counts as a structure with components Dim and Data.',
    'help': 'help alone lists the functions by topic. The examples are run when you ask, so their '
            'output is what this S prints.',
    'q': 'Typed alone, as a command. Back to the shell.',
    'printer': 'Plots are drawn with characters, as on a line printer, so any terminal can show '
               'them. They are kept back: a plot appears when you type show, or when the next plot '
               'starts. The manual calls this being one frame behind.',
    'tek14': 'The Tektronix 4014, a storage-tube terminal: what is drawn stays on the screen and '
             'more can be added, until the next plot erases the whole screen with a green flash. '
             'Here it is the screen beside the VT100.',
    'show': 'On the printer, shows the plot being built. On the Tektronix, draws it again.',
    'par': 'pch= sets the character used to plot points, "*" to begin with. Choosing a device '
           'resets it.',
    'plot': 'plot(x, y) plots y against x; plot(y) plots y against its index. type="l" joins the '
            'points with lines and "b" does both. log="x", "y" or "xy" makes axes logarithmic. The '
            'axis labels default to the names of the arguments.',
    'hist': 'Counts the data falling between tidy break points. nclass= suggests how many bars.',
    'barplot': 'One bar per value, in order.',
    'boxplot': 'The box runs from the lower to the upper hinge (Tukey\'s version of the '
               'quartiles) with the median across it; the whiskers reach the smallest and largest '
               'values.',
    'stem': 'Tukey\'s stem-and-leaf display: a histogram that keeps the digits. The header gives N, '
            'the median and the hinges. The first column is the depth, the count from the nearer '
            'end, left blank on the stem that holds the median; the second counts the leaves.',
    'points': 'Adds points to the current plot without redrawing its axes.',
    'lines': 'Joins the points in order with lines on the current plot.',
    'abline': 'abline(a, b) draws y = a + b*x across the plot. h= and v= draw horizontal and '
              'vertical lines.',
    'text': 'Writes each label centred at its point; labels= defaults to the numbers 1, 2, ...',
    'title': 'Adds or replaces the main title, subtitle and axis labels.',
}

EXAMPLES = {
    'c': 'c(1:3, 5, 7, 9)',
    'seq': 'seq(5); seq(2, 10, 2); seq(-1, 1, .5)',
    'rep': 'rep(1:3, 2); rep(c("Low", "High"), c(2, 3))',
    'abs': 'abs(c(-2, 0, 3))',
    'sqrt': 'sqrt(c(4, 9, 2))',
    'exp': 'exp(c(0, 1))',
    'log': 'log(c(1, exp(2)))',
    'log10': 'log10(c(1, 10, 1000))',
    'sin': 'sin(c(0, 1.5708))',
    'cos': 'cos(c(0, 3.14159))',
    'asin': 'asin(c(0, 1))',
    'acos': 'acos(c(1, 0))',
    'atan': 'atan(1) * 4',
    'ceiling': 'ceiling(c(-1.5, 2.1))',
    'floor': 'floor(c(-1.5, 2.9))',
    'trunc': 'trunc(c(-1.5, 2.9))',
    'round': 'round(3.14159, 2); round(c(1.4, 2.6)); round(1234, -2)',
    'sum': 'sum(1:10); sum(Month.length > 30)',
    'prod': 'prod(1:6)',
    'max': 'max(state.x77[,2]); max(Weekdays)',
    'min': 'min(c(3, 1, 2), 5)',
    'range': 'range(state.x77[,4])',
    'mean': 'mean(state.x77[,2]); mean(state.x77[,2], trim=.1)',
    'median': 'median(c(5, 1, 3, 2))',
    'var': 'var(c(1, 2, 3, 4))',
    'cumsum': 'cumsum(Month.length)',
    'diff': 'diff(c(1, 4, 9, 16))',
    'sort': 'sort(c(3, 1, 2)); sort(Weekdays)',
    'order': 'x <- c(30, 10, 20); order(x); x[order(x)]',
    'rank': 'rank(c(10, 30, 20, 20))',
    'rev': 'rev(1:5)',
    'match': 'match(c("NJ", "CA", "XX"), state.abb)',
    'unique': 'unique(c(3, 1, 3, 2, 1))',
    'all': 'all(Month.length > 27)',
    'any': 'any(Month.length == 29)',
    'len': 'len(state.name)',
    'mode': 'mode(1:3); mode(Weekdays)',
    'NA': 'x <- c(1, NA, 3); NA(x); x[!NA(x)]',
    'matrix': 'matrix(1:6, 2); matrix(1:6, ncol=2, byrow=T)',
    'nrow': 'nrow(state.x77)',
    'ncol': 'ncol(state.x77)',
    't': 't(matrix(1:6, 2))',
    'row': 'm <- matrix(1:9, 3); m[row(m) >= col(m)]',
    'col': 'm <- matrix(1:9, 3); m[row(m) == col(m)]',
    'cbind': 'cbind(1, c(2, 4, 6))',
    'rbind': 'rbind(1:3, 4:6)',
    'lowess': 'x <- state.x77[,2]; y <- state.x77[,4]; plot(x, y); lines(lowess(x, y)); show',
    'approx': 'fit <- lowess(state.x77[,2], state.x77[,4]); approx(fit, c(4000, 5000))',
    'ncomp': 'z <- approx(1:3, c(10, 20, 30), 2.5); ncomp(z); z$[1]; z$y',
    'define': 'define("backfit")',
    'mprint': 'mprint(mac.which)',
    'medit': 'medit(mac.which)',
    'rnorm': 'rnorm(5)',
    'runif': 'runif(3, 0, 10)',
    'list': 'list(pos=3)',
    'rm': 'x <- 1; y <- 2; list; rm(x, value=y * 10); list',
    'save': 'x <- 1:3; save(x); list(pos=2)',
    'get': 'get("Weekdays")',
    'assign': 'assign("y", 1:3); y',
    'read': 'm <- matrix(read("mydata"), ncol=4, byrow=T)',
    'print': 'print(matrix(1:4, 2), rowlab=c("one", "two"), collab=c("x", "y"))',
    'help': 'help(mean)',
    'q': 'q',
    'printer': 'printer; plot(1:10); show',
    'tek14': 'tek14; plot(state.x77[,2], state.x77[,4])',
    'show': 'plot(c(1, 4, 9, 16)); show',
    'par': 'par(pch="o"); plot(1:5); show',
    'plot': 'plot(state.x77[1:10,2], state.x77[1:10,4], xlab="Income", ylab="Life Exp"); show',
    'hist': 'hist(state.x77[,2]); show',
    'barplot': 'barplot(Month.length); show',
    'boxplot': 'boxplot(state.x77[,2]); show',
    'stem': 'stem(state.x77[1:10,2])',
    'points': 'plot(1:10); points(c(2, 8), c(8, 2), pch="o"); show',
    'lines': 'plot(1:10); lines(c(1, 10), c(10, 1)); show',
    'abline': 'plot(1:10); abline(0, 1); show',
    'text': 'plot(1:3); text(1:3, 1:3, labels=c("a", "b", "c")); show',
    'title': 'plot(1:5); title(main="Five points"); show',
}

NO_RUN = {'read', 'help', 'q', 'tek14', 'define', 'medit'}   # need a file, recurse, leave S, or draw on your screen

MANUAL = r"""
S(1)                                                                    S(1)

NAME
     S - an interactive language and system for data analysis and graphics

SYNOPSIS
     S

DESCRIPTION
     S was built in the statistics research departments of Bell Labora-
     tories, starting in 1976, by Rick Becker, John Chambers and Doug Dunn
     with Jean McRae and Judy Schilling.  Until then an analysis meant a
     Fortran program around SCS, the department's subroutine library, and
     for a small problem, a regression on 20 points, the programming was
     out of all proportion to the problem.  Routine data analysis should
     not need a Fortran program: S began as an interactive way into those
     subroutines and grew into a language.

     It first ran under GCOS on a Honeywell 645.  By October 1979 the UNIX
     version on the VAX was the main one; it is the system of the 1981
     manual, S: A Language and System for Data Analysis, that this machine
     imitates.  The name: every acronym proposed (Interactive SCS, Statis-
     tical Computing System, ...) contained an S, and with the C language
     as a precedent the system was simply called S.

USING S
     Type S to the shell.  S prompts with "> ", reads an expression,
     evaluates it and prints its value: the loop of read, parse, evaluate
     and print that has been the heart of S since 1976.

          > x <- c(1, -1, 2, -2, .5)
          > sort(x)
           -2.0 -1.0  0.5  1.0  2.0

     An expression that is not finished at the end of a line goes on to
     the next: S prompts with "+ ", like the UNIX shell.  A line starting
     with ! goes to the shell (!ed mydata), another UNIX idea.  # starts a
     comment.  q leaves S.

     Assignment is <-, taken from the language PPL (on some old terminals
     it was a single character), or _, or -> towards the right.  An
     assignment prints nothing; any other expression prints its value.  A
     name typed alone calls the function of that name with no arguments,
     list, show, q, and if there is none, prints the dataset.  A function
     called at the start of a line needs no parentheses: plot x,y is
     plot(x,y), help mean is help(mean).

DATA
     The basic data are vectors: numbers, character strings or logical
     values (T and F), all of one kind, with NA for a missing value.
     Operators and most functions work on every element at once, so most
     analyses need no loops.

     A vector can carry other vectors that describe it: a vector struc-
     ture.  A matrix is a vector of data, stored column by column, with a
     vector Dim holding the numbers of rows and columns.

          > m <- matrix(1:6, 2)          # 2 rows, filled by column

SUBSCRIPTS
     Subscripting is one of the most powerful operations in S.  x[i] takes
     the elements of x that i selects, and i may be

          positive numbers   x[c(1,1,3)]  repeats allowed, so the result
                                          can be longer than x
          negative numbers   x[-1]        all elements except these; an
                                          idea that may have begun with S
          logical values     x[x > 0]     the elements where i is T
          empty              x[]          everything

     A matrix takes one subscript per dimension, m[2,] or m[,c(1,3)], and
     can still be subscripted like a plain vector, m[m > 3].  On the left
     of an assignment, subscripts replace elements: x[x < 0] <- 0.

STRUCTURES
     Some functions return a structure: named components, each an S
     object.  lowess, the scatter plot smoother that W. S. Cleveland of
     Bell Laboratories published in 1979, returns one with components x
     and y, the points of the smooth curve:

          > fit <- lowess(x, y)
          > fit$y                  # one component; fit$[2] is the same

     A component name may be cut to any unique beginning, and ncomp
     counts the components.  A structure with components x and y is a
     graphical data structure: plot, points and lines take it in place
     of x and y, so lines(lowess(x, y)) draws the smooth through a
     scatter plot.  A matrix, too, can be taken apart as m$Dim and m$Data.

FUNCTIONS AND ARGUMENTS
     Apart from a few operators, everything in S is a call to a function,
     and the operators are shorthand for functions too.  Arguments are
     given by position or by name, mean(x, trim=.1), and a name may be cut
     to any unique beginning, mean(x, tr=.1).  Arguments left out take
     their defaults.  Positional and keyword arguments with defaults came
     from IBM 360 assembler and job control language, which also had to
     serve commands with many options of which a user sets only a few.  In
     the list below and in help, name= marks an optional argument.

LOOPS AND CONDITIONS
     if (cond) expr else expr     for (i in values) expr
     while (cond) expr            repeat expr        break    next

     Explicit loops came when users took on larger problems than looping
     over whole vectors could handle.  for (i in x) steps through the
     values of x without needing a counter.  Braces { } group expressions
     into one; inside them nothing is printed unless you call print.

DATASETS
     An assignment stores a dataset, and datasets last from one session to
     the next.  S searches three directories, in this order:

          working (1)   everything you assign
          save    (2)   what save(x) puts there: raw data, results to keep
          shared  (3)   datasets that come with S: Weekdays, Month.length,
                        state.name, state.abb, state.x77, votes.repub ...

     The plan was to clear out the working directory now and then and keep
     what mattered on the save directory.  As Becker later wrote, "people
     have a very hard time at cleaning up": the working directory was used
     for everything and the save directory seldom.  list shows a directory
     and rm removes datasets.

GRAPHICS
     S could draw from the start, through GR-Z, a device-independent
     graphics library written by Becker and Chambers.  Choose a device,
     then draw:

          printer   plots made of characters, for any terminal.  A plot
                    waits for show or for the next plot: one frame behind.
          tek14     a Tektronix 4014 storage-tube terminal, the screen
                    beside the VT100.  Drawings accumulate until the next
                    plot erases the screen.

ON THIS MACHINE
     This S is rebuilt from the 1981 manual, covering its Basic Use part.
     Macros (?name) are here: man macro.  Not here yet: assignment to
     components (z$x <- ...), time series, regress, diary, edit, again.
     Datasets last until you disconnect, not from one visit to the next.

SEE ALSO
     help(name) inside S: a function's documentation, with an example.
     R. A. Becker and J. M. Chambers, S: A Language and System for Data
     Analysis, Bell Laboratories, 1981.
     R. A. Becker, A Brief History of S, AT&T Bell Laboratories:
     """ + HISTORY + """
"""


def topic_of(name):
    return next(t for t in TOPICS if name in t[2].split())


def wrap(text, indent=5):
    return textwrap.fill(text, 76, initial_indent=' ' * indent, subsequent_indent=' ' * indent) + '\n'


class _Capture:
    def __init__(self):
        self.out = []

    def write(self, text):
        self.out.append(text)

    def check(self):
        pass

    def readline(self):
        raise s.EOF


def run_example(src):
    """Run an example in a scratch S, so it can't touch your datasets or your screen."""
    io = _Capture()
    try:
        s.Interp(io).run(src)
    except s.SError as e:
        io.out.append(f'Error: {e}\n')
    return ''.join(io.out)


def help_page(name):
    b = s.BUILTINS[name]
    title, _, names = topic_of(name)
    usage = b.usage(name)
    out = [usage + title.rjust(max(2, 76 - len(usage))) + '\n\n', wrap(b.doc[0].upper() + b.doc[1:] + '.')]
    if name in DETAILS:
        out.append(wrap(DETAILS[name]))
    ex = EXAMPLES[name]
    shown = [ex] if len(ex) <= 64 else ex.split('; ')     # one statement per prompt when long
    lines = ['> ' + part for part in shown]
    if name not in NO_RUN:
        lines += run_example(ex).rstrip('\n').split('\n')
    pad = ' ' * max(0, min(10, 80 - max(map(len, lines))))  # as far right as the widest line allows
    out.append('\n     Example\n' + ''.join((pad + line).rstrip() + '\n' for line in lines))
    others = [n for n in names.split() if n != name]
    out.append('\n' + wrap('See also: ' + ' '.join(others) + '.'))
    return ''.join(out)


def index(indent=5):
    out = []
    for title, intro, names in TOPICS:
        out.append('\n' + ' ' * indent + title + '\n' + wrap(intro, indent + 3))
        for n in names.split():
            b = s.BUILTINS[n]
            usage, col = b.usage(n), indent + 33
            doc = textwrap.wrap(b.doc, 76 - col)
            if len(usage) > 28:
                out.append(f'{" " * (indent + 3)}{usage}\n')
            else:
                out.append(f'{" " * (indent + 3)}{usage:<30}{doc.pop(0)}\n')
            out += [' ' * col + line + '\n' for line in doc]
    return ''.join(out)


def help_index():
    return ('help(name) prints the documentation for the function name, with an example.\n'
            'man S, from the shell, explains S itself.\n'
            + ''.join(f'\n{title}\n' + wrap(' '.join(names.split()), 3) for title, _, names in TOPICS))


def manual():
    return MANUAL + '\nFUNCTIONS' + index() + '\n'

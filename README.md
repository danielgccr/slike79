# Compute S like 1979

A DEC VT100 in your browser, logged into a simulated UNIX/32V, running **S**: the
statistical language John Chambers, Rick Becker and colleagues built at Bell Laboratories
from 1976, as described in the 1981 manual *S: A Language and System for Data Analysis*.

Bell Labs S was never released, so this one is rebuilt in Python from that manual. The
UNIX around it is simulated too, with `sh`, `ed`, pipes and `troff`, so you can analyse data
and write up the results the way it was done then.

```
$ S
> x <- c(1,-1,2,-2,.5); sort(x)
 -2.0 -1.0  0.5  1.0  2.0
> m <- matrix(read("mydata"), ncol=4, byrow=T)
Read 40 items
> printer; plot(m[,2], m[,4], main="Ten States, 1977"); show
```

## What you can do

- **S as in the 1981 manual**
  - **Language:** vectors, matrices, the manual's subscripts (repeats, negative, logical), structures and `$`, command form (`plot x,y`) and `_` assignment.
  - **Statistics:** about 80 functions, including Cleveland's `lowess` (1979) and `approx`. Their output matches R's to the digits S prints.
  - **Data:** the 1977 state data on the shared directory.
  - **Help:** `help(name)` gives a documentation page with an example that is run live.
- **Graphics on period devices**
  - `printer` draws character plots in the terminal, one frame behind, as the manual describes.
  - `tek14` draws on a Tektronix 4014 storage tube beside the VT100. Pictures build up until the next plot erases the screen.
- **The S macro processor** (§4 of the manual): `MACRO … END` files read with `define`, plus `mprint`, `medit`, `?name(args)` calls and every built-in (`IFELSE`, `LOOP`, `PROMPT`…). `man macro` teaches it, ending with a what-if backfitting (GAM) macro.
- **A Seventh Edition-style shell**
  - **Shell:** pipes (`|` and `^`), redirection, and shell procedures with `$1`.
  - **Commands:** `ed`, `tr`, `sort`, `uniq`, `comm`, `chmod`, `stty` and more.
  - **Typesetting:** `eqn`, `neqn`, `troff`, `nroff -ms` and `col`. `troff` output opens as a phototypesetter proof over the page.
- **The 1982 Bell Labs film:** `man unix1982` replays its two demonstrations, Kernighan's spelling-checker pipeline and Cherry's `eqn | troff`.
- **Reports, 1981 style**
  - **What existed:** run S on its own (`S < analysis > results`), then format a memo that pulls the results in with `.so`.
  - **What could have existed:** `spp`, a troff preprocessor that runs S blocks inside a document. It's a clearly labelled what-if, roughly a 1981 R Markdown (`man spp`).
- **Two keyboards**
  - **Modern** (the default): Backspace, arrow keys, history and Ctrl-C.
  - **1979:** the V7 terminal driver. `#` erases, `@` kills the line, Delete interrupts, and you fix Backspace with `stty erase '^h'`.
- **On the page:** a reference card and worked examples. Each example's transcript was produced by this machine, and a *Type it* button enters it for you.

Log in with any lowercase name; there are no passwords. Your home directory holds the
example files (`mydata`, `report`, `backfit`, …). Start with `man`, `man S` and
`man unix1982`.

## Running it

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/danielgccr/slike79.git
cd slike79
uv run uvicorn app:app --reload
```

Open <http://localhost:8000>. The page loads xterm.js and htmx from jsDelivr and its fonts
from Google Fonts, so the browser needs to be online.

### Tests

```sh
uv run python test_s.py && uv run python test_unix.py
```

Plain `assert` scripts, with no framework. They check:
- S output against the manual's own examples;
- `lowess` and the backfitting macro against R;
- `ed`, the shell and the film's demonstrations;
- the typesetters and `spp`;
- that every manual page and help page fits on an 80-column screen;
- the guards described below.

## Deploying

`railway.json` deploys to [Railway](https://railway.com): connect the repository or run
`railway up`. It runs **one replica**, because each visitor's session lives in that
process's memory. A redeploy disconnects everyone, and the page then offers to dial again.

The server uses about 52 MB idle and about 76 MB with 50 sessions, so it fits Railway's
Free plan (0.5 GB). Guards keep a public machine within those bounds:

| Limit | Default | Visitors see |
|---|---|---|
| Dial-in lines | 25 at once (`SLIKE79_LINES`) | *All lines busy. Try again later.* |
| Idle line | 15 minutes (`SLIKE79_IDLE`, seconds) | *No input for 15 minutes: line dropped.* |
| S datasets | 500,000 values per visitor | an S error asking them to `rm` some |
| One S expression | 30 seconds | an S error; S prompts again |
| Files | 2 MB per visitor | `No space left on device` |
| Output | 4 MB per command | the command stops |
| Input line | 256 characters in 1979 mode (V7's `CANBSIZ`), 4,096 in modern mode | the terminal bell |
| WebSocket frame | 64 KB (`--ws-max-size`) | the connection closes |

## How it is built

FastAPI serves the page and one WebSocket per terminal. Each terminal runs the simulated
machine in its own thread. Line editing happens in one place, the terminal line discipline,
just as in UNIX: the programs only ever receive finished lines. That's why the 1979 keyboard
needed no change to `sh`, `ed` or S.

| File | What it is |
|---|---|
| `app.py` | FastAPI: the page, `/card` and `/examples` (HTMX fragments), the `/tty` WebSocket, the guards |
| `vt.py` | The terminal line discipline: modern and 1979 modes, interrupts, history |
| `unix.py` | Login, `sh`, the in-memory file system, the commands, `ed`, `spp`, the manual pages |
| `s.py` | S: lexer, parser, evaluator, printing, builtins, structures, `lowess` |
| `smacro.py` | The S macro processor, and `man macro` |
| `sgraph.py` | S graphics: the line-printer and Tektronix 4014 devices, `stem` |
| `sdoc.py` | `man S` and `help(name)`, with live examples |
| `typeset.py` | `eqn`, `neqn`, `troff` (to an SVG proof), `nroff`, and the `-ms` macros |
| `sexamples.py` | The worked examples, run through the machine to produce their transcripts |
| `sdata.py` | The shared datasets, taken from R's `datasets` and `cluster` packages |
| `static/` | The VT100 page: xterm.js, the 4014 pane, the reference card and examples |

Graphics travel inside the terminal stream as private escape sequences: `ESC ] 1979 ;` for
the Tektronix and `ESC ] 1980 ;` for troff proofs. The page shows them as images.

## Faithful, reconstructed, invented

Built from these sources:
- R. A. Becker and J. M. Chambers, *S: A Language and System for Data Analysis*, Bell Laboratories, 1981.
- R. A. Becker, [*A Brief History of S*](https://sas.uwaterloo.ca/~rwoldfor/software/R-code/historyOfS.pdf), AT&T Bell Laboratories.
- The Seventh Edition source and manual pages on [TUHS](https://www.tuhs.org/).
- [*AT&T Archives: The UNIX Operating System* (1982)](https://sparsenotes.com/posts/2026/07/unix-att-archives-1982/), for the film's demonstrations.

Where the manual is silent, the code and the manual pages say what was reconstructed:
- the wording of the "dataset not found" error;
- the layout used to print structures;
- whether S printed prompts when reading from a file.

Two parts are deliberate what-ifs and say so: `spp`, and the backfitting macro, since GAMs
reached S only in 1991.

Some features are period-faithful on purpose, even when that's less convenient:
- `tr` knows only octal escapes, so `'\n'` is the letter n and newline is `'\012'`;
- `^` is a pipe in `sh`;
- a lone name runs the function of that name before it prints a dataset;
- 1981 `lowess` removes duplicate x values;
- nobody's plot can go into a troff document.

A few things are modern conveniences: the default keyboard, `clear`, and the line,
memory and time limits.

Not yet here:
- time series and `regress`;
- assigning to structure components;
- `apply`, `diary`, `edit` and `again`;
- `tbl`, `pic` and `grap`;
- datasets that persist from one visit to the next.

## Credits

The state data are the 1977 U.S. figures that S shipped with, as kept in R's `datasets`
package; `votes.repub` comes from R's `cluster` package. The terminal is
[xterm.js](https://xtermjs.org/), the partial page loads use [htmx](https://htmx.org/), and the
VT100 type is [VT323](https://fonts.google.com/specimen/VT323) by Peter Hull.

"""The terminal line discipline: the only place that knows how a line was typed.

Programs run in a thread, write their prompt, and call readline() for a finished line,
exactly as they would read from a 1979 terminal driver. Two disciplines:

  modern  Backspace erases, arrows move and recall history, Ctrl-C interrupts, Ctrl-U kills.
  1979    the Seventh Edition driver: '#' erases, '@' kills, DEL interrupts, ^\\ quits,
          \\# and \\@ type the characters themselves, no history, and nothing is ever
          rubbed out on screen. `stty erase ^h` remaps erase, as users did then.

The WebSocket side calls feed() with keystrokes, set_mode() from the page switch,
and hangup() on disconnect.
"""
import queue
import re

ESCAPES = re.compile(r'\x1b\][^\x07]*\x07|\x1b\[[0-9;?]*[A-Za-z]')   # OSC pictures, CSI controls


class Interrupt(Exception):
    pass


class EOF(Exception):
    pass


class Hangup(BaseException):
    """Connection gone. BaseException so programs' `except Exception` can't swallow it."""


class Tty:
    def __init__(self, send):
        self.send = send            # thread-safe callable(str) to the browser
        self.q = queue.Queue()
        self.pending = ''
        self.intr = self.dead = False
        self.mode = 'modern'
        self.chars = {'erase': '#', 'kill': '@', 'intr': '\x7f', 'quit': '\x1c'}
        self.hist = {}
        self.tail = ''              # what is on the cursor's line: the prompt, when a program reads

    @property
    def max_line(self):
        return 256 if self.mode == '1979' else 4096     # V7's input buffer, CANBSIZ, held 256

    def set_mode(self, mode):
        if mode in ('modern', '1979'):
            self.mode = mode

    def interrupt_keys(self):
        return ('\x03',) if self.mode == 'modern' else (self.chars['intr'], self.chars['quit'])

    def feed(self, data):
        if any(k in data for k in self.interrupt_keys()):
            self.intr = True        # seen by check() while a program is computing
        if self.q.qsize() < 1000:   # typeahead beyond that is dropped, as a full tty buffer did
            self.q.put(data)

    def hangup(self):
        self.dead = True
        self.q.put(None)

    def write(self, s):
        self.tail = ESCAPES.sub('', (self.tail + s).rsplit('\n', 1)[-1])
        self.send(s.replace('\r\n', '\n').replace('\n', '\r\n'))

    def check(self):
        """Call from long loops: raises Interrupt after an interrupt key, flushing typeahead like a real tty."""
        if self.dead:
            raise Hangup
        if self.intr:
            self.intr, self.pending = False, ''
            while not self.q.empty():
                if self.q.get_nowait() is None:
                    raise Hangup
            self.write('^C\n' if self.mode == 'modern' else '\n')
            raise Interrupt

    def getc(self):
        while not self.pending:
            data = self.q.get()
            if data is None:
                raise Hangup
            self.pending = data
        c, self.pending = self.pending[0], self.pending[1:]
        return c

    def readline(self):
        """One finished line, without its newline. Raises Interrupt or EOF."""
        prompt = self.tail
        return self.line_1979() if self.mode == '1979' else self.line_modern(prompt)

    # -- the Seventh Edition driver
    def line_1979(self):
        buf, ch = [], self.chars
        while True:
            c = self.getc()
            if c in '\r\n':
                self.write('\n')
                return ''.join(buf)
            if c in (ch['intr'], ch['quit']):
                self.intr = False
                self.write('\n')
                raise Interrupt
            if c == '\x04':
                if not buf:
                    raise EOF
                return ''.join(buf)
            escaped = buf and buf[-1] == '\\'
            if c in (ch['erase'], ch['kill']) and escaped:
                buf[-1] = c                     # \# and \@ are the characters themselves
                self.send(c)
            elif c == ch['erase']:
                if buf:
                    buf.pop()
                self.send(c)                    # echoed, never rubbed out
            elif c == ch['kill']:
                buf.clear()
                self.send(c + '\r\n')
            elif len(buf) >= self.max_line:
                self.send('\x07')                # line full: ring the bell
            else:
                buf.append(c)
                self.send(c)                    # even escape sequences: arrows move the cursor

    # -- the modern discipline
    def key(self):
        """One keypress; escape sequences (arrows, Home, Delete...) come back whole."""
        c = self.getc()
        if c != '\x1b' or not self.pending:
            return c
        seq = c + self.getc()
        if seq[1] in '[O':
            while self.pending:
                ch = self.getc()
                seq += ch
                if ch.isalpha() or ch == '~':
                    break
        return seq

    def line_modern(self, prompt):
        buf, pos = [], 0
        h = self.hist.setdefault(prompt, [])    # history per prompt: sh, S, ed each get their own
        hi = len(h)

        def redraw():
            # ponytail: assumes prompt+line fit on one 80-column row
            back = len(buf) - pos
            self.send('\r' + prompt + ''.join(buf) + '\x1b[K' + (f'\x1b[{back}D' if back else ''))

        while True:
            k = self.key()
            if k in ('\r', '\n'):
                self.intr = False
                self.write('\n')
                line = ''.join(buf)
                if line.strip() and (not h or h[-1] != line):
                    h.append(line)
                return line
            if k == '\x03':                                   # Ctrl-C
                self.intr = False
                self.write('^C\n')
                raise Interrupt
            if k == '\x04':                                   # Ctrl-D
                if not buf:
                    self.write('\n')
                    raise EOF
                if pos < len(buf):
                    del buf[pos]
                    redraw()
            elif k in ('\x7f', '\x08'):                       # Backspace
                if pos:
                    pos -= 1
                    del buf[pos]
                    redraw()
            elif k == '\x1b[3~':                              # Delete
                if pos < len(buf):
                    del buf[pos]
                    redraw()
            elif k == '\x15':                                 # Ctrl-U
                del buf[:pos]
                pos = 0
                redraw()
            elif k == '\x17':                                 # Ctrl-W
                j = pos
                while j and buf[j - 1] == ' ':
                    j -= 1
                while j and buf[j - 1] != ' ':
                    j -= 1
                del buf[j:pos]
                pos = j
                redraw()
            elif k in ('\x01', '\x1b[H', '\x1bOH'):           # Home / Ctrl-A
                pos = 0
                redraw()
            elif k in ('\x05', '\x1b[F', '\x1bOF'):           # End / Ctrl-E
                pos = len(buf)
                redraw()
            elif k in ('\x1b[D', '\x1bOD', '\x02'):
                pos = max(0, pos - 1)
                redraw()
            elif k in ('\x1b[C', '\x1bOC', '\x06'):
                pos = min(len(buf), pos + 1)
                redraw()
            elif k in ('\x1b[A', '\x1bOA', '\x10'):           # Up: older history
                if hi > 0:
                    hi -= 1
                    buf = list(h[hi])
                    pos = len(buf)
                    redraw()
            elif k in ('\x1b[B', '\x1bOB', '\x0e'):           # Down: newer history
                if hi < len(h):
                    hi += 1
                    buf = list(h[hi]) if hi < len(h) else []
                    pos = len(buf)
                    redraw()
            elif k == '\x0c':                                 # Ctrl-L
                self.send('\x1b[H\x1b[2J')
                redraw()
            elif len(k) == 1 and (k >= ' ' or k == '\t') and len(buf) >= self.max_line:
                self.send('\x07')                # line full: ring the bell
            elif len(k) == 1 and (k >= ' ' or k == '\t'):
                buf.insert(pos, k)
                pos += 1
                if pos == len(buf):
                    self.send(k)
                else:
                    redraw()

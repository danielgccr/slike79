"""Compute S like 1979: a VT100 in the browser, wired to a simulated UNIX/32V running S."""
import asyncio
import functools
import html
import os
import pathlib
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import s
import sdoc
import sexamples
import unix
import vt

HERE = pathlib.Path(__file__).parent
app = FastAPI(title='Compute S like 1979')
app.mount('/static', StaticFiles(directory=HERE / 'static'), name='static')


@app.middleware('http')
async def revalidate(request, call_next):
    """Always check for a newer page and scripts: a cached term.js with a new index.html breaks the page."""
    response = await call_next(request)
    if request.url.path == '/' or request.url.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-cache'
    return response


@app.get('/')
def index():
    return FileResponse(HERE / 'static' / 'index.html')


@app.get('/card', response_class=HTMLResponse)
def card():
    """Quick reference card, built from the same tables the shell, ed and S use."""
    def section(title, rows):
        body = ''.join(f'<dt>{html.escape(k)}</dt><dd>{html.escape(v)}</dd>' for k, v in rows)
        return f'<section><h2>{title}</h2><dl>{body}</dl></section>'
    keys = [('Backspace', 'erase'), ('Ctrl-C', 'interrupt'), ('Ctrl-D', 'end of file / log out'),
            ('Ctrl-U Ctrl-W', 'kill line / word'), ('Up Down', 'history'), ('Ctrl-L', 'clear screen')]
    keys_1979 = [('#', 'erase (echoed, never rubbed out)'), ('@', 'kill the line'),
                 ('Delete', 'interrupt (DEL)'), ('Ctrl-D', 'end of file / log out'),
                 ("stty erase '^h'", 'make Backspace erase, as 1979 users did')]
    return (section('Keys, modern', keys) + section('Keys, 1979', keys_1979)
            + section('sh', [(k, d) for k, (_, d) in unix.CMDS.items()])
            + section('ed', unix.ED_HELP)
            + ''.join(section(f'S: {title.lower()}', [(s.BUILTINS[n].usage(n), s.BUILTINS[n].doc)
                                                      for n in names.split()])
                      for title, _, names in sdoc.TOPICS))


@app.get('/examples', response_class=HTMLResponse)
@functools.cache                      # the transcripts are run once, the first time anyone asks
def examples():
    """Worked examples: a first statistical analysis, with output produced by this S."""
    return sexamples.page()


LINES = int(os.environ.get('SLIKE79_LINES', 25))        # dial-in lines; the 32V's dz board had 16
IDLE = int(os.environ.get('SLIKE79_IDLE', 15 * 60))    # seconds without a keystroke before hanging up
BUSY, HUNG_UP = 4000, 4001                             # close codes the page turns into messages
in_use = 0                                             # one event loop, so a plain counter is safe


@app.websocket('/tty')
async def tty(ws: WebSocket):
    global in_use
    await ws.accept()
    if in_use >= LINES:                    # every modem in the hunt group is taken: a busy signal
        await ws.close(code=BUSY, reason='all lines busy')
        return
    in_use += 1
    loop = asyncio.get_running_loop()
    out = asyncio.Queue()

    def send(data):
        try:
            loop.call_soon_threadsafe(out.put_nowait, data)
        except RuntimeError:        # event loop already gone
            pass

    term = vt.Tty(send)

    def run():
        # ponytail: one thread per terminal, fine for tens of users; asyncio programs if it ever needs hundreds
        try:
            unix.session(term)
        except vt.Hangup:
            pass
        finally:
            send(None)

    threading.Thread(target=run, daemon=True).start()

    async def pump():
        while (data := await out.get()) is not None:
            await ws.send_text(data)

    sender = asyncio.create_task(pump())
    idle = False
    try:
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive(), IDLE)
            except asyncio.TimeoutError:
                idle = True
                break
            if msg['type'] == 'websocket.disconnect':
                break
            if msg.get('text') is not None:         # keystrokes
                term.feed(msg['text'])
            elif msg.get('bytes') is not None:      # control from the page, e.g. b'mode 1979'
                ctl = msg['bytes'].decode('ascii', 'ignore').split()
                if len(ctl) == 2 and ctl[0] == 'mode':
                    term.set_mode(ctl[1])
    except WebSocketDisconnect:
        pass
    finally:
        in_use -= 1
        term.hangup()
        sender.cancel()
        if idle:                           # an idle line is hung up, as time-sharing systems did
            try:
                await ws.close(code=HUNG_UP, reason='idle')
            except RuntimeError:
                pass

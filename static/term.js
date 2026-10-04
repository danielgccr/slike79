// xterm.js <-> /tty WebSocket. Keystrokes go up as text; the server's line discipline
// does all echo and editing. Control messages (the keys switch) go up as binary frames.
const term = new Terminal({
  cols: 80, rows: 24,
  fontFamily: 'VT323, monospace', fontSize: 22, lineHeight: 1,
  cursorBlink: true, cursorStyle: 'block', scrollback: 2000,
  theme: { background: '#0d1110', foreground: '#e3ebf0', cursor: '#e3ebf0',
           selectionBackground: 'rgba(227, 235, 240, 0.3)' },
});

let ws = null;
const send = data => { if (ws && ws.readyState === WebSocket.OPEN) ws.send(data); };

// ---- keys: modern line editing, or the 1979 driver with a VT100 keyboard
const HELP = {
  modern: 'Backspace erases, ↑ recalls a line, Ctrl-C interrupts.',
  1979: "# erases, @ kills the line, Delete interrupts. Make Backspace erase with stty erase '^h'.",
};
let mode = 'modern';
try { mode = localStorage.getItem('keys') === '1979' ? '1979' : 'modern'; } catch {}
const setMode = m => {
  mode = m;
  document.querySelector(`input[name=keys][value="${m}"]`).checked = true;
  document.getElementById('keys-help').textContent = HELP[m];
  send(new TextEncoder().encode('mode ' + m));
  try { localStorage.setItem('keys', m); } catch {}
};
document.querySelectorAll('input[name=keys]').forEach(r =>
  r.addEventListener('change', () => { setMode(r.value); term.focus(); }));

const proof = document.getElementById('proof');
const closeProof = () => { proof.hidden = true; term.focus(); };
proof.addEventListener('click', closeProof);

term.attachCustomKeyEventHandler(e => {
  if (e.key === 'Escape' && !proof.hidden) {
    if (e.type === 'keydown') closeProof();
    return false;
  }
  // A VT100's BACKSPACE key sends BS and its DELETE key sends DEL (the 1979 interrupt).
  if (mode === '1979' && (e.key === 'Backspace' || e.key === 'Delete')) {
    if (e.type === 'keydown') send(e.key === 'Backspace' ? '\x08' : '\x7f');
    return false;
  }
  return true;
});

const scrolling = () => (matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');

// ---- Reference card and Worked examples: toggles. HTMX loads each panel on the first click only.
document.querySelectorAll('[data-toggles]').forEach(button => button.addEventListener('click', () => {
  const panel = document.getElementById(button.dataset.toggles);
  panel.hidden = !panel.hidden;
  button.setAttribute('aria-pressed', String(!panel.hidden));
  if (!panel.hidden) panel.scrollIntoView({ behavior: scrolling(), block: 'start' });
}));

// ---- worked examples: Type it enters an example's lines at the S prompt, as if typed
document.addEventListener('click', e => {
  const button = e.target.closest('.type-it');
  if (!button) return;
  for (const line of JSON.parse(button.dataset.type)) send(line + '\r');
  vt.scrollIntoView({ behavior: scrolling(), block: 'center' });
  term.focus();
});

// ---- pictures arrive inside private OSC sequences. Shown as <img>, so nothing in the SVG can run.
const asImage = svg => 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);

// 1979: S on the Tektronix 4014 beside the terminal. "E;" = erase the screen first.
const tek = document.getElementById('tek');
const tube = tek.querySelector('.tube');
term.parser.registerOscHandler(1979, data => {
  const erase = data.startsWith('E;');
  tek.querySelector('img').src = asImage(erase ? data.slice(2) : data);
  if (tek.hidden) { tek.hidden = false; fit(); }
  if (erase) { tube.classList.remove('flash'); void tube.offsetWidth; tube.classList.add('flash'); }
  return true;
});

// 1980: a page proof from troff.
term.parser.registerOscHandler(1980, svg => {
  proof.querySelector('img').src = asImage(svg);
  proof.hidden = false;
  return true;
});

const HANGUPS = {
  4000: 'All lines busy. Try again later.',
  4001: 'No input for 15 minutes: line dropped.',
};

function connect() {
  term.write('Dialing...\r\n');
  ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/tty`);
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => setMode(mode);
  const input = term.onData(send);
  ws.onmessage = e => term.write(e.data);
  ws.onclose = e => {
    input.dispose();
    const why = HANGUPS[e.code] || 'Carrier lost.';
    term.write(`\r\n\x1b[7m ${why} Press any key to dial again. \x1b[0m\r\n`);
    const redial = term.onData(() => { redial.dispose(); term.reset(); connect(); });
  };
}

// Scale the VT100 down when the screen is narrow, or to make room for the 4014 beside it.
const vt = document.getElementById('case');
let natural = 0;
function fit() {
  if (!natural) return;
  let room = document.documentElement.clientWidth - 32;
  if (!tek.hidden && room >= 1000) room -= 420 + 32;
  vt.style.zoom = Math.min(1, room / natural);
}

document.fonts.load('22px VT323').finally(() => {
  term.open(document.getElementById('screen'));
  natural = vt.offsetWidth;
  fit();
  addEventListener('resize', fit);
  document.getElementById('keys-help').textContent = HELP[mode];
  document.querySelector(`input[name=keys][value="${mode}"]`).checked = true;
  document.body.classList.add('on');
  connect();
  term.focus();
});

import express from 'express';
import pino from 'pino';
import QRCode from 'qrcode';
import {
  makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  downloadMediaMessage,
} from '@whiskeysockets/baileys';
import { rmSync, mkdirSync, existsSync } from 'node:fs';

const PORT = parseInt(process.env.PORT || '3000', 10);
const AUTH_DIR = process.env.AUTH_DIR || '/data/auth';

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });

// Ring buffer for GET /logs
const logRing = [];
const LOG_RING_SIZE = 200;
const ringStream = {
  write(msg) {
    try {
      const parsed = JSON.parse(msg);
      const line = `[${new Date(parsed.time).toISOString()}] ${parsed.level} ${parsed.msg || ''}`;
      logRing.push(line);
      if (logRing.length > LOG_RING_SIZE) logRing.shift();
    } catch {
      logRing.push(msg.toString());
    }
    process.stdout.write(msg);
  },
};
const ringLogger = pino({ level: 'info' }, ringStream);

const state = {
  sock: null,
  status: 'disconnected', // disconnected | qr_pending | connecting | connected
  qr: null, // current QR string
  jid: null,
  deviceName: null,
  lastSeen: null,
};

async function start() {
  if (!existsSync(AUTH_DIR)) mkdirSync(AUTH_DIR, { recursive: true });

  const { state: authState, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  state.status = 'connecting';
  const sock = makeWASocket({
    version,
    auth: authState,
    logger: ringLogger,
    printQRInTerminal: false,
    browser: ['Notify', 'Desktop', '1.0'],
  });
  state.sock = sock;

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      state.qr = qr;
      state.status = 'qr_pending';
      ringLogger.info('QR code updated');
    }
    if (connection === 'open') {
      state.status = 'connected';
      state.qr = null;
      state.jid = sock.user?.id || null;
      state.deviceName = sock.user?.name || null;
      state.lastSeen = new Date().toISOString();
      ringLogger.info({ jid: state.jid }, 'connected');
    }
    if (connection === 'close') {
      const code = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = code !== DisconnectReason.loggedOut;
      state.status = 'disconnected';
      state.jid = null;
      ringLogger.warn({ code, shouldReconnect }, 'connection closed');
      if (shouldReconnect) setTimeout(start, 2000);
    }
  });
}

start().catch((e) => ringLogger.error({ err: e.message }, 'start failed'));

// --- HTTP API ---
const app = express();
app.use(express.json({ limit: '25mb' }));

const requireConnected = (req, res, next) => {
  if (state.status !== 'connected' || !state.sock) {
    return res.status(503).json({ error: 'not connected', status: state.status });
  }
  next();
};

app.get('/status', (req, res) => {
  res.json({
    state: state.status,
    jid: state.jid,
    device_name: state.deviceName,
    last_seen: state.lastSeen,
  });
});

app.get('/qr', async (req, res) => {
  if (state.status === 'connected') return res.status(404).json({ error: 'already connected' });
  if (!state.qr) return res.status(404).json({ error: 'no qr available yet' });
  const png = await QRCode.toBuffer(state.qr, { width: 320, margin: 2 });
  res.type('image/png').send(png);
});

app.get('/logs', (req, res) => {
  const limit = Math.min(parseInt(req.query.limit || '50', 10), LOG_RING_SIZE);
  res.json({ lines: logRing.slice(-limit) });
});

app.post('/logout', async (req, res) => {
  try {
    if (state.sock) await state.sock.logout().catch(() => {});
  } catch {}
  state.status = 'disconnected';
  state.jid = null;
  state.qr = null;
  rmSync(AUTH_DIR, { recursive: true, force: true });
  mkdirSync(AUTH_DIR, { recursive: true });
  setTimeout(start, 500);
  res.json({ ok: true });
});

app.post('/restart', async (req, res) => {
  try {
    if (state.sock) state.sock.end(new Error('restart requested'));
  } catch {}
  setTimeout(start, 500);
  res.json({ ok: true });
});

app.post('/validate', requireConnected, async (req, res) => {
  const { number } = req.body || {};
  if (!number) return res.status(422).json({ error: 'number required' });
  try {
    const results = await state.sock.onWhatsApp(number);
    const first = results?.[0];
    if (first?.exists) return res.json({ exists: true, jid: first.jid });
    return res.json({ exists: false, jid: null });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/send/text', requireConnected, async (req, res) => {
  const { jid, text } = req.body || {};
  if (!jid || !text) return res.status(422).json({ error: 'jid and text required' });
  try {
    const r = await state.sock.sendMessage(jid, { text });
    res.json({ message_id: r.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/send/media', requireConnected, async (req, res) => {
  const { jid, url, base64, caption, mimetype } = req.body || {};
  if (!jid || (!url && !base64)) {
    return res.status(422).json({ error: 'jid + (url or base64) required' });
  }
  try {
    const buffer = base64 ? Buffer.from(base64, 'base64') : undefined;
    const source = buffer ? { buffer } : { url };
    const mt = mimetype || 'application/octet-stream';
    let content;
    if (mt.startsWith('image/')) content = { image: source.buffer ?? { url: source.url }, caption };
    else if (mt.startsWith('video/')) content = { video: source.buffer ?? { url: source.url }, caption };
    else if (mt.startsWith('audio/')) content = { audio: source.buffer ?? { url: source.url }, mimetype: mt };
    else content = { document: source.buffer ?? { url: source.url }, mimetype: mt, caption };
    const r = await state.sock.sendMessage(jid, content);
    res.json({ message_id: r.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post('/send/ptt', requireConnected, async (req, res) => {
  const { jid, audio_base64 } = req.body || {};
  if (!jid || !audio_base64) return res.status(422).json({ error: 'jid and audio_base64 required' });
  try {
    const buffer = Buffer.from(audio_base64, 'base64');
    const r = await state.sock.sendMessage(jid, {
      audio: buffer,
      ptt: true,
      mimetype: 'audio/ogg; codecs=opus',
    });
    res.json({ message_id: r.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, () => ringLogger.info({ port: PORT }, 'baileys sidecar listening'));

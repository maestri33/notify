import express from "express";
import pino from "pino";
import QRCode from "qrcode";
import { WebSocketServer } from "ws";
import { createServer } from "http";
import {
  makeWASocket,
  DisconnectReason,
  fetchLatestBaileysVersion,
} from "@whiskeysockets/baileys";
import { useSqliteAuthState } from "./sqlite-auth-state.js";
import {
  upsertContact,
  getContact,
  listContacts,
  searchContacts,
  insertMessage,
  getMessage,
  listMessages,
  recentMessages,
  countMessages,
} from "./db.js";

const PORT = parseInt(process.env.PORT || "3000", 10);

const logger = pino({ level: process.env.LOG_LEVEL || "info" });

// Ring buffer for GET /logs
const logRing = [];
const LOG_RING_SIZE = 200;
const ringStream = {
  write(msg) {
    try {
      const parsed = JSON.parse(msg);
      const line = `[${new Date(parsed.time).toISOString()}] ${parsed.level} ${parsed.msg || ""}`;
      logRing.push(line);
      if (logRing.length > LOG_RING_SIZE) logRing.shift();
    } catch {
      logRing.push(msg.toString());
    }
    process.stdout.write(msg);
  },
};
const ringLogger = pino({ level: "info" }, ringStream);

const state = {
  sock: null,
  status: "disconnected",
  qr: null,
  jid: null,
  deviceName: null,
  lastSeen: null,
};

let restartTimer = null;
let authStateHandle = null;

// ── WebSocket broadcast ────────────────────────────────────────────────────

/** @type {Set<import("ws").WebSocket>} */
const wsClients = new Set();

function broadcast(data) {
  const msg = JSON.stringify(data);
  for (const ws of wsClients) {
    if (ws.readyState === 1) {
      try { ws.send(msg); } catch {}
    }
  }
}

// ── Socket start ───────────────────────────────────────────────────────────

async function start() {
  authStateHandle = await useSqliteAuthState();
  const { state: authState, saveCreds } = authStateHandle;
  const { version } = await fetchLatestBaileysVersion();

  state.status = "connecting";
  broadcast({ event: "connection.update", data: { status: "connecting" } });

  const sock = makeWASocket({
    version,
    auth: authState,
    logger: ringLogger,
    printQRInTerminal: false,
    browser: ["Notify", "Desktop", "1.0"],
    fireInitQueries: false,
    defaultQueryTimeoutMs: 60_000,
    connectTimeoutMs: 30_000,
    keepAliveIntervalMs: 25_000,
    markOnlineOnConnect: false,
    shouldSyncHistoryMessage: () => false,
  });
  state.sock = sock;

  sock.ev.on("creds.update", (update) => {
    Object.assign(authState.creds, update);
    saveCreds();
    broadcast({ event: "creds.update", data: { me: authState.creds.me?.id } });
  });

  // Incoming messages → SQLite + WebSocket push
  sock.ev.on("messages.upsert", ({ messages }) => {
    const pushed = [];
    for (const msg of messages) {
      try { insertMessage(msg); pushed.push(msg); } catch {}
    }
    if (pushed.length) {
      broadcast({ event: "messages.upsert", data: { messages: pushed } });
    }
  });

  // Contacts → SQLite + WebSocket push
  sock.ev.on("contacts.update", (contacts) => {
    const pushed = [];
    for (const c of contacts) {
      try {
        upsertContact(c.id, {
          name: c.name,
          notify: c.notify,
          verifiedName: c.verifiedName,
          isWhatsappUser: true,
        });
        pushed.push(c);
      } catch {}
    }
    if (pushed.length) {
      broadcast({ event: "contacts.update", data: { contacts: pushed } });
    }
  });

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      state.qr = qr;
      state.status = "qr_pending";
      broadcast({ event: "connection.update", data: { status: "qr_pending" } });
      ringLogger.info("QR code updated");
    }
    if (connection === "open") {
      state.status = "connected";
      state.qr = null;
      state.jid = sock.user?.id || null;
      state.deviceName = sock.user?.name || null;
      state.lastSeen = new Date().toISOString();
      ringLogger.info({ jid: state.jid }, "connected");
      broadcast({
        event: "connection.update",
        data: {
          status: "connected",
          jid: state.jid,
          deviceName: state.deviceName,
          lastSeen: state.lastSeen,
        },
      });
    }
    if (connection === "close") {
      const code = lastDisconnect?.error?.output?.statusCode;
      const shouldReconnect = code !== DisconnectReason.loggedOut;
      state.status = "disconnected";
      state.jid = null;
      ringLogger.warn({ code, shouldReconnect }, "connection closed");
      broadcast({
        event: "connection.update",
        data: {
          status: "disconnected",
          code,
          shouldReconnect,
        },
      });
      if (shouldReconnect) {
        clearTimeout(restartTimer);
        restartTimer = setTimeout(start, 2_000);
      }
    }
  });
}

start().catch((e) => ringLogger.error({ err: e.message }, "start failed"));

// ── HTTP API ────────────────────────────────────────────────────────────────

const app = express();
app.use(express.json({ limit: "25mb" }));

const requireConnected = (req, res, next) => {
  if (state.status !== "connected" || !state.sock) {
    return res.status(503).json({ error: "not connected", status: state.status });
  }
  next();
};

app.get("/status", (req, res) => {
  res.json({
    state: state.status,
    jid: state.jid,
    device_name: state.deviceName,
    last_seen: state.lastSeen,
  });
});

app.get("/qr", async (req, res) => {
  if (state.status === "connected")
    return res.status(404).json({ error: "already connected" });
  if (!state.qr)
    return res.status(404).json({ error: "no qr available yet" });
  const png = await QRCode.toBuffer(state.qr, { width: 320, margin: 2 });
  res.type("image/png").send(png);
});

app.get("/logs", (req, res) => {
  const limit = Math.min(parseInt(req.query.limit || "50", 10), LOG_RING_SIZE);
  res.json({ lines: logRing.slice(-limit) });
});

app.post("/logout", async (req, res) => {
  try {
    if (state.sock) await state.sock.logout().catch(() => {});
  } catch {}
  state.status = "disconnected";
  state.jid = null;
  state.qr = null;
  clearTimeout(restartTimer);
  if (authStateHandle) authStateHandle.clear();
  setTimeout(start, 500);
  res.json({ ok: true });
});

app.post("/restart", async (req, res) => {
  try {
    if (state.sock) state.sock.end(new Error("restart requested"));
  } catch {}
  clearTimeout(restartTimer);
  setTimeout(start, 500);
  res.json({ ok: true });
});

app.post("/validate", requireConnected, async (req, res) => {
  const { phone } = req.body || {};
  if (!phone) return res.status(422).json({ error: "phone required" });
  try {
    const results = await state.sock.onWhatsApp(phone);
    const first = results?.[0];
    if (first?.exists) return res.json({ exists: true, jid: first.jid });
    return res.json({ exists: false, jid: null });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/send/text", requireConnected, async (req, res) => {
  const { jid, text } = req.body || {};
  if (!jid || !text)
    return res.status(422).json({ error: "jid and text required" });
  try {
    const r = await state.sock.sendMessage(jid, { text });
    res.json({ message_id: r.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/send/media", requireConnected, async (req, res) => {
  const { jid, url, base64, caption, mimetype } = req.body || {};
  if (!jid || (!url && !base64)) {
    return res.status(422).json({ error: "jid + (url or base64) required" });
  }
  try {
    const buffer = base64 ? Buffer.from(base64, "base64") : undefined;
    const source = buffer ? { buffer } : { url };
    const mt = mimetype || "application/octet-stream";
    let content;
    if (mt.startsWith("image/"))
      content = { image: source.buffer ?? { url: source.url }, caption };
    else if (mt.startsWith("video/"))
      content = { video: source.buffer ?? { url: source.url }, caption };
    else if (mt.startsWith("audio/"))
      content = { audio: source.buffer ?? { url: source.url }, mimetype: mt };
    else
      content = { document: source.buffer ?? { url: source.url }, mimetype: mt, caption };
    const r = await state.sock.sendMessage(jid, content);
    res.json({ message_id: r.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/send/ptt", requireConnected, async (req, res) => {
  const { jid, audio_base64 } = req.body || {};
  if (!jid || !audio_base64)
    return res.status(422).json({ error: "jid and audio_base64 required" });
  try {
    const buffer = Buffer.from(audio_base64, "base64");
    const r = await state.sock.sendMessage(jid, {
      audio: buffer,
      ptt: true,
      mimetype: "audio/ogg; codecs=opus",
    });
    res.json({ message_id: r.key.id });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Send by phone (auto-resolve JID) ────────────────────────────────────────

async function resolvePhone(phone) {
  const cleaned = String(phone).replace(/\D/g, "");
  const results = await state.sock.onWhatsApp(`${cleaned}@s.whatsapp.net`);
  const first = results?.[0];
  if (!first?.exists) return null;
  return first.jid;
}

app.post("/send/text/phone", requireConnected, async (req, res) => {
  const { phone, text } = req.body || {};
  if (!phone) return res.status(422).json({ error: "phone required" });
  if (!text) return res.status(422).json({ error: "text required" });
  try {
    const jid = await resolvePhone(phone);
    if (!jid) return res.status(404).json({ error: "phone not on WhatsApp" });
    const r = await state.sock.sendMessage(jid, { text });
    res.json({ message_id: r.key.id, jid });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/send/media/phone", requireConnected, async (req, res) => {
  const { phone, url, base64, caption, mimetype } = req.body || {};
  if (!phone) return res.status(422).json({ error: "phone required" });
  if (!url && !base64) return res.status(422).json({ error: "url or base64 required" });
  try {
    const jid = await resolvePhone(phone);
    if (!jid) return res.status(404).json({ error: "phone not on WhatsApp" });
    const buffer = base64 ? Buffer.from(base64, "base64") : undefined;
    const source = buffer ? { buffer } : { url };
    const mt = mimetype || "application/octet-stream";
    let content;
    if (mt.startsWith("image/"))
      content = { image: source.buffer ?? { url: source.url }, caption };
    else if (mt.startsWith("video/"))
      content = { video: source.buffer ?? { url: source.url }, caption };
    else if (mt.startsWith("audio/"))
      content = { audio: source.buffer ?? { url: source.url }, mimetype: mt };
    else
      content = { document: source.buffer ?? { url: source.url }, mimetype: mt, caption };
    const r = await state.sock.sendMessage(jid, content);
    res.json({ message_id: r.key.id, jid });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.post("/send/ptt/phone", requireConnected, async (req, res) => {
  const { phone, audio_base64 } = req.body || {};
  if (!phone) return res.status(422).json({ error: "phone required" });
  if (!audio_base64) return res.status(422).json({ error: "audio_base64 required" });
  try {
    const jid = await resolvePhone(phone);
    if (!jid) return res.status(404).json({ error: "phone not on WhatsApp" });
    const buffer = Buffer.from(audio_base64, "base64");
    const r = await state.sock.sendMessage(jid, {
      audio: buffer,
      ptt: true,
      mimetype: "audio/ogg; codecs=opus",
    });
    res.json({ message_id: r.key.id, jid });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Broadcast (same message to multiple phones) ─────────────────────────────

app.post("/send/text/broadcast", requireConnected, async (req, res) => {
  const { phones, text } = req.body || {};
  if (!phones || !Array.isArray(phones) || !phones.length)
    return res.status(422).json({ error: "phones array required" });
  if (!text) return res.status(422).json({ error: "text required" });
  const results = [];
  for (const phone of phones) {
    try {
      const jid = await resolvePhone(phone);
      if (!jid) {
        results.push({ phone, status: "not_found" });
        continue;
      }
      const r = await state.sock.sendMessage(jid, { text });
      results.push({ phone, jid, status: "sent", message_id: r.key.id });
    } catch (e) {
      results.push({ phone, status: "error", error: e.message });
    }
  }
  res.json({ results });
});

app.post("/send/ptt/broadcast", requireConnected, async (req, res) => {
  const { phones, audio_base64 } = req.body || {};
  if (!phones || !Array.isArray(phones) || !phones.length)
    return res.status(422).json({ error: "phones array required" });
  if (!audio_base64) return res.status(422).json({ error: "audio_base64 required" });
  const buffer = Buffer.from(audio_base64, "base64");
  const results = [];
  for (const phone of phones) {
    try {
      const jid = await resolvePhone(phone);
      if (!jid) {
        results.push({ phone, status: "not_found" });
        continue;
      }
      const r = await state.sock.sendMessage(jid, {
        audio: buffer,
        ptt: true,
        mimetype: "audio/ogg; codecs=opus",
      });
      results.push({ phone, jid, status: "sent", message_id: r.key.id });
    } catch (e) {
      results.push({ phone, status: "error", error: e.message });
    }
  }
  res.json({ results });
});

// ── Contacts API ────────────────────────────────────────────────────────────

app.get("/contacts", (req, res) => {
  const limit = Math.min(parseInt(req.query.limit || "100", 10), 500);
  const offset = parseInt(req.query.offset || "0", 10);
  if (req.query.q) {
    return res.json({ contacts: searchContacts(req.query.q, limit, offset) });
  }
  res.json({ contacts: listContacts(limit, offset) });
});

app.get("/contacts/:jid", (req, res) => {
  const c = getContact(req.params.jid);
  if (!c) return res.status(404).json({ error: "contact not found" });
  res.json(c);
});

// ── Messages API ────────────────────────────────────────────────────────────

app.get("/messages", (req, res) => {
  const jid = req.query.jid;
  const limit = Math.min(parseInt(req.query.limit || "50", 10), 200);
  const offset = parseInt(req.query.offset || "0", 10);

  if (jid) {
    const msgs = listMessages(jid, limit, offset);
    return res.json({ messages: msgs });
  }
  const msgs = recentMessages(limit);
  res.json({ messages: msgs });
});

app.get("/messages/count", (req, res) => {
  res.json({ count: countMessages() });
});

app.get("/messages/:id", (req, res) => {
  const m = getMessage(req.params.id);
  if (!m) return res.status(404).json({ error: "message not found" });
  res.json(m);
});

// ── Groups API ──────────────────────────────────────────────────────────────

app.get("/groups", requireConnected, async (req, res) => {
  try {
    const groups = await state.sock.groupFetchAllParticipating();
    const list = Object.entries(groups || {}).map(([jid, g]) => ({
      jid,
      subject: g.subject,
      subject_owner: g.subjectOwner,
      subject_time: g.subjectTime,
      size: g.size,
      creation: g.creation,
      owner: g.owner,
      desc: g.desc,
      announce: g.announce,
      restrict: g.restrict,
      ephemeral: g.ephemeral,
      is_group: true,
    }));
    res.json({ groups: list });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/groups/:jid", requireConnected, async (req, res) => {
  try {
    const metadata = await state.sock.groupMetadata(req.params.jid);
    res.json(metadata);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/groups/:jid/members", requireConnected, async (req, res) => {
  try {
    const metadata = await state.sock.groupMetadata(req.params.jid);
    res.json({
      jid: metadata.id,
      subject: metadata.subject,
      participants: metadata.participants,
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/groups/:jid/invite", requireConnected, async (req, res) => {
  try {
    const code = await state.sock.groupInviteCode(req.params.jid);
    res.json({
      jid: req.params.jid,
      invite_code: code,
      invite_link: `https://chat.whatsapp.com/${code}`,
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── User Profile API ────────────────────────────────────────────────────────

app.get("/users/:jid", requireConnected, async (req, res) => {
  try {
    const jid = req.params.jid;
    const [ppHigh, ppLow, userStatus, contact] = await Promise.allSettled([
      state.sock.profilePictureUrl(jid, "image").catch(() => null),
      state.sock.profilePictureUrl(jid).catch(() => null),
      state.sock.fetchStatus(jid).catch(() => null),
      (async () => {
        const c = getContact(jid);
        if (c) return c;
        const sc = state.sock.contacts?.[jid];
        if (sc) return { jid, name: sc.name, notify: sc.notify, verified_name: sc.verifiedName };
        return null;
      })(),
    ]);

    res.json({
      jid,
      profile_picture_url_high: ppHigh.status === "fulfilled" ? ppHigh.value : null,
      profile_picture_url_low: ppLow.status === "fulfilled" ? ppLow.value : null,
      status: userStatus.status === "fulfilled" ? userStatus.value : null,
      contact: contact.status === "fulfilled" ? contact.value : null,
    });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── Contacts sync ──────────────────────────────────────────────────────────

app.post("/contacts/sync", requireConnected, async (req, res) => {
  try {
    const fetched = [];
    const contactJids = Object.keys(state.sock.contacts || {});
    for (const jid of contactJids) {
      const c = state.sock.contacts[jid];
      upsertContact(jid, {
        name: c.name,
        notify: c.notify,
        verifiedName: c.verifiedName,
        isWhatsappUser: true,
      });
      fetched.push(jid);
    }
    res.json({ synced: fetched.length });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

// ── HTTP + WebSocket server ─────────────────────────────────────────────────

const server = createServer(app);

const wss = new WebSocketServer({ server, path: "/ws" });

wss.on("connection", (ws) => {
  wsClients.add(ws);
  ringLogger.info("ws client connected, total=" + wsClients.size);

  // Send current state immediately
  ws.send(JSON.stringify({
    event: "connection.update",
    data: {
      status: state.status,
      jid: state.jid,
      deviceName: state.deviceName,
    },
  }));

  ws.on("close", () => {
    wsClients.delete(ws);
    ringLogger.info("ws client disconnected, total=" + wsClients.size);
  });

  ws.on("error", () => {
    wsClients.delete(ws);
  });
});

server.listen(PORT, () =>
  ringLogger.info({ port: PORT }, "baileys sidecar listening (http+ws)")
);

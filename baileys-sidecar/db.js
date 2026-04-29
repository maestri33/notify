import Database from "better-sqlite3";
import { existsSync, mkdirSync } from "fs";
import { BufferJSON } from "@whiskeysockets/baileys";

const DB_PATH = process.env.BAILEYS_DB_PATH || "/var/lib/notify/baileys.db";

const dbDir = DB_PATH.replace(/\/[^/]+$/, "");
if (!existsSync(dbDir)) mkdirSync(dbDir, { recursive: true });

const db = new Database(DB_PATH);
db.pragma("journal_mode = WAL");
db.pragma("busy_timeout = 5000");
db.pragma("foreign_keys = ON");

db.exec(`
  CREATE TABLE IF NOT EXISTS baileys_creds (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    creds_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS baileys_keys (
    type TEXT NOT NULL,
    id TEXT NOT NULL,
    data BLOB,
    PRIMARY KEY (type, id)
  ) WITHOUT ROWID;

  CREATE TABLE IF NOT EXISTS baileys_contacts (
    jid TEXT PRIMARY KEY,
    name TEXT,
    notify TEXT,
    verified_name TEXT,
    is_whatsapp_user INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
  );

  CREATE TABLE IF NOT EXISTS baileys_messages (
    id TEXT PRIMARY KEY,
    remote_jid TEXT NOT NULL,
    from_me INTEGER NOT NULL DEFAULT 0,
    body TEXT,
    timestamp INTEGER,
    message_json TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_msg_jid ON baileys_messages(remote_jid);
  CREATE INDEX IF NOT EXISTS idx_msg_ts ON baileys_messages(timestamp DESC);

  CREATE TABLE IF NOT EXISTS baileys_media (
    id TEXT PRIMARY KEY,
    message_id TEXT,
    url TEXT,
    mimetype TEXT,
    filename TEXT,
    size INTEGER,
    local_path TEXT,
    created_at TEXT NOT NULL
  );
`);

const now = () => new Date().toISOString();

// ── Creds ──────────────────────────────────────────────────────────────────

const stmtGetCreds = db.prepare("SELECT creds_json FROM baileys_creds WHERE id = 1");
const stmtSetCreds = db.prepare(
  "INSERT OR REPLACE INTO baileys_creds (id, creds_json, updated_at) VALUES (1, ?, ?)"
);

export function getCreds() {
  const row = stmtGetCreds.get();
  return row ? JSON.parse(row.creds_json, BufferJSON.reviver) : null;
}

export function saveCreds(creds) {
  stmtSetCreds.run(JSON.stringify(creds, BufferJSON.replacer), now());
}

// ── Keys ───────────────────────────────────────────────────────────────────

const stmtGetKeysByType = db.prepare(
  "SELECT id, data FROM baileys_keys WHERE type = ? AND id IN (SELECT value FROM json_each(?))"
);
const stmtSetManyKeys = db.prepare(
  "INSERT OR REPLACE INTO baileys_keys (type, id, data) VALUES (?, ?, ?)"
);
const stmtClearKeys = db.prepare("DELETE FROM baileys_keys");

export function getKeys(type, ids) {
  const result = {};
  const rows = stmtGetKeysByType.all(type, JSON.stringify(ids));
  for (const row of rows) result[row.id] = row.data;
  return result;
}

export function setKeys(type, entries) {
  const insert = db.transaction((items) => {
    for (const [id, data] of items) {
      stmtSetManyKeys.run(type, id, data);
    }
  });
  insert(entries);
}

export function clearKeys() {
  stmtClearKeys.run();
}

// ── Contacts ───────────────────────────────────────────────────────────────

const stmtUpsertContact = db.prepare(`
  INSERT INTO baileys_contacts (jid, name, notify, verified_name, is_whatsapp_user, updated_at)
  VALUES (?, ?, ?, ?, ?, ?)
  ON CONFLICT(jid) DO UPDATE SET
    name = excluded.name,
    notify = excluded.notify,
    verified_name = excluded.verified_name,
    is_whatsapp_user = excluded.is_whatsapp_user,
    updated_at = excluded.updated_at
`);

const stmtGetContact = db.prepare("SELECT * FROM baileys_contacts WHERE jid = ?");
const stmtListContacts = db.prepare(
  "SELECT * FROM baileys_contacts ORDER BY notify, name LIMIT ? OFFSET ?"
);
const stmtSearchContacts = db.prepare(`
  SELECT * FROM baileys_contacts
  WHERE name LIKE ? OR notify LIKE ? OR jid LIKE ?
  ORDER BY notify, name LIMIT ? OFFSET ?
`);

export function upsertContact(jid, data) {
  stmtUpsertContact.run(
    jid,
    data.name || null,
    data.notify || null,
    data.verifiedName || null,
    data.isWhatsappUser ? 1 : 0,
    now()
  );
}

export function getContact(jid) {
  return stmtGetContact.get(jid) || null;
}

export function listContacts(limit = 100, offset = 0) {
  return stmtListContacts.all(limit, offset);
}

export function searchContacts(query, limit = 50, offset = 0) {
  const q = `%${query}%`;
  return stmtSearchContacts.all(q, q, q, limit, offset);
}

// ── Messages ───────────────────────────────────────────────────────────────

const stmtInsertMsg = db.prepare(`
  INSERT OR IGNORE INTO baileys_messages (id, remote_jid, from_me, body, timestamp, message_json)
  VALUES (?, ?, ?, ?, ?, ?)
`);

const stmtGetMsg = db.prepare("SELECT * FROM baileys_messages WHERE id = ?");
const stmtListMsgs = db.prepare(`
  SELECT * FROM baileys_messages
  WHERE remote_jid = ?
  ORDER BY timestamp DESC LIMIT ? OFFSET ?
`);
const stmtRecentMsgs = db.prepare(`
  SELECT * FROM baileys_messages ORDER BY timestamp DESC LIMIT ?
`);
const stmtCountMsgs = db.prepare("SELECT COUNT(*) as n FROM baileys_messages");

export function insertMessage(msg) {
  const body =
    msg.message?.conversation ||
    msg.message?.extendedTextMessage?.text ||
    msg.message?.imageMessage?.caption ||
    msg.message?.videoMessage?.caption ||
    null;
  stmtInsertMsg.run(
    msg.key.id,
    msg.key.remoteJid,
    msg.key.fromMe ? 1 : 0,
    body,
    msg.messageTimestamp || null,
    JSON.stringify(msg)
  );
}

export function getMessage(id) {
  return stmtGetMsg.get(id) || null;
}

export function listMessages(jid, limit = 50, offset = 0) {
  return stmtListMsgs.all(jid, limit, offset);
}

export function recentMessages(limit = 50) {
  return stmtRecentMsgs.all(limit);
}

export function countMessages() {
  return stmtCountMsgs.get().n;
}

// ── Transaction helper ─────────────────────────────────────────────────────

export { db as default };

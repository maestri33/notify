import { BufferJSON, initAuthCreds } from "@whiskeysockets/baileys";
import {
  getCreds,
  saveCreds,
  getKeys,
  setKeys,
  clearKeys,
} from "./db.js";

/**
 * SQLite-backed AuthenticationState for Baileys.
 *
 * Stores credentials in `baileys_creds` and signal keys in `baileys_keys`.
 * Uses BufferJSON serialization compatible with Baileys' file-based auth.
 */
export async function useSqliteAuthState() {
  let creds = getCreds();
  if (!creds) {
    creds = initAuthCreds();
    saveCreds(creds);
  }

  const keys = {
    get(type, ids) {
      const result = getKeys(type, ids);
      const deserialized = {};
      for (const [id, data] of Object.entries(result)) {
        if (data === null) {
          deserialized[id] = null;
        } else {
          try {
            deserialized[id] = JSON.parse(data.toString("utf8"), BufferJSON.reviver);
          } catch {
            deserialized[id] = data;
          }
        }
      }
      return deserialized;
    },

    set(data) {
      const entries = {};
      for (const [type, items] of Object.entries(data)) {
        if (!items) continue;
        for (const [id, value] of Object.entries(items)) {
          if (!entries[type]) entries[type] = [];
          const serialized = value === null
            ? null
            : Buffer.from(JSON.stringify(value, BufferJSON.replacer), "utf8");
          entries[type].push([id, serialized]);
        }
      }
      for (const [type, items] of Object.entries(entries)) {
        setKeys(type, items);
      }
    },

    clear() {
      clearKeys();
    },
  };

  return {
    state: { creds, keys },
    saveCreds: () => saveCreds(creds),
    clear: () => {
      clearKeys();
      saveCreds(initAuthCreds());
    },
  };
}

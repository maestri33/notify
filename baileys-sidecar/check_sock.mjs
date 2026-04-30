import { makeWASocket, fetchLatestBaileysVersion } from "@whiskeysockets/baileys";
import { useSqliteAuthState } from "./sqlite-auth-state.js";

const auth = await useSqliteAuthState();
const { version } = await fetchLatestBaileysVersion();

const sock = makeWASocket({
    version, auth: auth.state,
    browser: ["Notify", "Desktop", "1.0"],
    fireInitQueries: false,
    connectTimeoutMs: 15_000,
    markOnlineOnConnect: false,
    shouldSyncHistoryMessage: () => false,
});

await new Promise((resolve, reject) => {
    sock.ev.on("connection.update", (u) => {
        if (u.connection === "open") resolve();
        if (u.connection === "close") reject(new Error("close"));
    });
    setTimeout(() => reject(new Error("timeout")), 20_000);
});

const keys = Object.keys(sock.contacts || {});
console.log("contacts:", keys.length);
console.log("sample:", keys.slice(0, 10));
if (keys.length) {
    const first = sock.contacts[keys[0]];
    console.log("first:", JSON.stringify(first).slice(0, 400));
}
process.exit(0);

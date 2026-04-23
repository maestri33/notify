# Deploy — LXC on Proxmox (Production Guide)

Target: a single LXC container on Proxmox running Docker + Compose. The stack is internal-only; the dashboard must never be exposed to the public internet. Access it exclusively over VPN.

---

## 1. Provision the LXC

On the Proxmox host, create a new CT with these settings:

| Setting | Value |
|---|---|
| **OS template** | Ubuntu 24.04 LTS |
| **Unprivileged** | yes |
| **Features** | `keyctl=1,nesting=1` (required for Docker) |
| **vCPU** | 2 (minimum) — use 4 if heavy TTS / ElevenLabs use expected |
| **RAM** | 2 GB (minimum) — use 4 GB for heavy TTS |
| **Disk** | 20 GB (minimum) |
| **Network** | Static IP on your LAN/VPN subnet |
| **Hostname** | `notify` |

> **Why `nesting=1`?** Docker needs the ability to create nested namespaces inside an unprivileged LXC. Without it, `docker run` fails.

---

## 2. Install Docker inside the CT

```bash
apt update && apt install -y ca-certificates curl git ufw

# Add Docker's official GPG key and repository
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release; echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list

apt update && apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
```

Verify: `docker run --rm hello-world` should complete successfully.

---

## 3. Configure UFW firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp                          # SSH
ufw allow from <vpn-subnet> to any port 8001    # Dashboard / API (VPN only)
ufw allow from <vpn-subnet> to any port 3000    # Baileys sidecar (optional, VPN only)
ufw --force enable
ufw status
```

Replace `<vpn-subnet>` with your actual VPN/LAN CIDR (e.g. `10.10.0.0/24`).

> Port 8001 is the FastAPI / HTMX dashboard. Port 3000 is the Baileys HTTP sidecar — only expose it if you need direct sidecar access from other hosts.

---

## 4. Clone and configure

```bash
git clone <repo> /opt/notify
cd /opt/notify
cp .env.example .env
# .env is already correct for a default deploy.
# Tune LOG_LEVEL / APP_ENV if needed — all external credentials go in the dashboard.
```

All external credentials (SMTP, SMS Gateway, ElevenLabs) are configured **in the dashboard** at `/config`, not in `.env`.

---

## 5. First deploy

```bash
docker compose build
docker compose up -d
docker compose ps   # confirm all services are healthy
```

Expected healthy services: `redis`, `api`, `worker-whatsapp`, `worker-sms`, `worker-email`, `baileys`.

---

## 6. Systemd service (auto-start on CT boot)

Create `/etc/systemd/system/notify.service`:

```ini
[Unit]
Description=Notify notification service
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/notify
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable --now notify
```

From now on the stack starts automatically whenever the CT boots.

---

## 7. First-run checklist

1. Open `http://<lxc-ip>:8001/baileys` → the page shows a QR code. Scan it with WhatsApp → *Linked devices*. After pairing the status card flips to **connected**.
2. Open `http://<lxc-ip>:8001/config` → fill in SMTP, SMS Gateway, and ElevenLabs credentials. Use the *Test* button for each section.
3. Alternatively, use the CLI:
   ```bash
   docker compose exec api notify config set --smtp-host mail.example.com --smtp-port 587 ...
   ```
4. Smoke test:
   ```bash
   docker compose exec api notify status
   ```

---

## 8. Updates

```bash
cd /opt/notify
git pull
docker compose build
docker compose up -d   # database migrations run automatically on api container restart
```

No manual migration steps required — Alembic / SQLModel migrations are applied on startup.

---

## 9. Backup

### Automated cron (`/etc/cron.d/notify-backup`)

```
15 3 * * *  root  cd /opt/notify && ./scripts/backup.sh /opt/notify/backups >> /var/log/notify-backup.log 2>&1
5  4 * * 0  root  find /opt/notify/backups -name 'notify-*.tar.gz' -mtime +30 -delete
```

- Daily at 03:15: snapshot SQLite DB + Baileys auth state.
- Weekly cleanup on Sunday at 04:05: delete backups older than 30 days.

### Manual backup

```bash
./scripts/backup.sh /opt/notify/backups
```

---

## 10. Monitoring

```bash
docker compose ps                          # container status + health
./scripts/logs.sh                          # tail all service logs
./scripts/logs.sh worker-email             # tail a specific service
docker compose exec api notify status      # application-level health check
```

---

## Volumes

| Volume | Contents | Notes |
|---|---|---|
| `app-data` | SQLite database (`notify.db`) | Back this up daily |
| `redis-data` | Redis AOF persistence | Survives restarts |
| `baileys-auth` | WhatsApp multi-device auth state | Losing this forces a new QR scan |

> Never remove these volumes without a backup. Losing `baileys-auth` means WhatsApp must be re-paired from scratch.

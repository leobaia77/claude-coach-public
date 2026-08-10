# Remote access — reach the coach from anywhere

The dashboard runs always-on at **http://localhost:8787** (this Mac) and
**http://192.168.1.128:8787** (any device on your home Wi-Fi) via the launchd
service. To reach it from *anywhere* (cellular, other networks), add ONE of the
secure options below.

> ⚠️ This serves your health data. **Do NOT** use a plain
> `cloudflared tunnel --url http://localhost:8787` quick tunnel — that creates a
> **public, unauthenticated** URL anyone could open. Use a private/locked option.

---

## Option A — Tailscale  (recommended: simplest, private, free)

A private encrypted mesh between *your* devices only. No domain, no public exposure.

1. On the Mac:
   ```bash
   brew install tailscale && sudo tailscale up
   ```
   (or install the Tailscale app). Note the Mac's name, e.g. `leos-mac`.
2. Install **Tailscale on your iPhone**, sign in with the **same account**.
3. From the phone, anywhere:
   ```
   http://leos-mac.<your-tailnet>.ts.net:8787      (MagicDNS)
   — or —
   http://100.x.x.x:8787                            (the Mac's Tailscale IP: `tailscale ip -4`)
   ```
Only your logged-in devices can reach it. Bookmark it on your phone home screen.

---

## Option B — Cloudflare named tunnel + Access  (stable public hostname, email-gated)

Best if you want a clean URL like `coach.yourdomain.com`. Requires a domain on Cloudflare.

1. Authenticate (opens a browser):
   ```bash
   cloudflared tunnel login
   ```
2. Create the tunnel + DNS route:
   ```bash
   cloudflared tunnel create coach
   cloudflared tunnel route dns coach coach.yourdomain.com
   ```
3. Config `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: coach
   credentials-file: /Users/YOUR_USERNAME/.cloudflared/<TUNNEL_UUID>.json
   ingress:
     - hostname: coach.yourdomain.com
       service: http://localhost:8787
     - service: http_status:404
   ```
4. **Lock it to you** — in the Cloudflare dashboard → Zero Trust → Access →
   add an application for `coach.yourdomain.com` with a policy allowing only your
   email. Now every visit requires your login.
5. Run it always-on:
   ```bash
   cp deploy/com.leo.coach-cloudflared.plist ~/Library/LaunchAgents/
   launchctl load -w ~/Library/LaunchAgents/com.leo.coach-cloudflared.plist
   ```

---

## Managing the always-on app service

```bash
# status
launchctl list | grep coach-dashboard
# logs
tail -f dashboard/logs/coach.out.log dashboard/logs/coach.err.log
# stop / start
launchctl unload ~/Library/LaunchAgents/com.leo.coach-dashboard.plist
launchctl load -w ~/Library/LaunchAgents/com.leo.coach-dashboard.plist
# after you change dashboard code: rebuild, then restart
npm run build --prefix dashboard
launchctl kickstart -k gui/$(id -u)/com.leo.coach-dashboard
```

## Enable the chat (one-time)

The chat agent uses your Claude subscription headlessly, which needs a token:
```bash
claude setup-token            # opens browser, prints a token
echo 'CLAUDE_CODE_OAUTH_TOKEN=<paste-token>' >> dashboard/.env
launchctl kickstart -k gui/$(id -u)/com.leo.coach-dashboard   # restart to pick it up
```
Until then, all data panels / reports / goals work; only chat shows a setup hint.

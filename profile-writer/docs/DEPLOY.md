# Deploying for the demo

Two parts, hosted separately:

```
 web/  (static dashboard)               app/  (Python server)
 GitHub Pages or Netlify  ──HTTPS──▶    Render, or your laptop + a tunnel
   Replay mode: no server needed          /api  (dashboard data, token-protected)
   Live mode: Connect → server URL+token  /webhook  (WhatsApp, Meta-signed)
```

The dashboard is public but holds nothing secret: Replay shows a recorded run on synthetic
chats, and Live mode needs the server's access token, which you type in at demo time. It
is kept only in that browser tab.

## 1. Frontend

**GitHub Pages** (public repo, or a paid GitHub plan for private repos):
1. A repo admin opens *Settings → Pages → Source* and picks **GitHub Actions**.
2. Merge to `main`. The workflow `.github/workflows/pages.yml` (repo root) publishes `profile-writer/web/`.
   To deploy from another branch: *Settings → Environments → github-pages*, add the branch,
   then run the workflow by hand (*Actions → Deploy dashboard → Run workflow*).
3. The site is at `https://<owner>.github.io/<repo>/`.

**Netlify** (works with private repos on the free plan): *Add new site → Import from Git*,
pick the repo and branch. `netlify.toml` already sets the publish folder to `web`. Or drag
the `web/` folder onto app.netlify.com/drop for a one-off copy.

Either way the build refuses to publish if anything in `web/` looks like an API key. (`netlify.toml` and `render.yaml` sit at the repo root and point into `profile-writer/`.)

## 2. Server

**Render (recommended for the demo):** *New → Blueprint* → this repo. `render.yaml`
creates the service and generates `DASHBOARD_TOKEN` and `PSEUDONYM_KEY`. In the service's
*Environment* tab fill in:
- `ALLOWED_ORIGINS`: the frontend's address without a trailing slash, e.g.
  `https://bigmoud.github.io` (Pages) or `https://noora-demo.netlify.app`
- `ANTHROPIC_API_KEY`: from the Corps/Noora Console account, with a spend cap set there
- The WhatsApp values from `WHATSAPP.md`, then `WHATSAPP_LIVE=true`

Notes for the free plan: it sleeps after ~15 minutes idle and takes about a minute to wake,
so open the dashboard before you present. Its disk is wiped on restart, so the demo data
resets to the 4 seeded families (that's fine for a demo).

**Your laptop + a tunnel (fallback):**
```bash
ALLOWED_ORIGINS=https://bigmoud.github.io python3 -m app.server
ngrok http 8000            # or: cloudflared tunnel --url http://localhost:8000
```
Use the tunnel's `https://` address both as the dashboard's server URL and for the
WhatsApp webhook. The token is printed in the terminal.

## 3. Connect

Open the hosted dashboard → **Connect to live server** → paste the server URL and
`DASHBOARD_TOKEN` → *Connect*. The bar turns blue and says "Live · connected to …".
"Couldn't connect" almost always means `ALLOWED_ORIGINS` doesn't match the frontend's
address exactly.

## 4. Refresh the replay (optional)

After changing the prompt or rules, re-record so Replay matches the code:
```bash
python3 -m scripts.record_replay      # uses Claude if ANTHROPIC_API_KEY is set (~$0.004)
```
It runs the demo script through the real pipeline on a throwaway database and rewrites
`web/replay.json`.

## Plan B, in order

1. Live WhatsApp on the phone →
2. Live server, messages typed into the dashboard's simulator →
3. **Replay** (no internet needed beyond loading the page) →
4. Screen recording.

# Setting up Pashu Arogya on a new PC / laptop

Everything needed to run the project is in this repository. Nothing has to be copied from
another machine — the SQLite database is created and seeded automatically on first run.

## 1. Install the prerequisites (one time)

| Tool | Version | Download | Check it works |
|---|---|---|---|
| Git | any recent | https://git-scm.com/downloads | `git --version` |
| Python | **3.11 or newer** | https://www.python.org/downloads/ | `python --version` |
| Node.js | **22 LTS** (20.19+ also OK) | https://nodejs.org | `node --version` |

> **Windows:** in the Python installer tick **"Add python.exe to PATH"**.
> On Windows the command is `python`; on macOS/Linux it is usually `python3`.

## 2. Clone the repository

```bash
git clone https://github.com/Rehan-Shaikh00/livestock-health-mvp.git
cd livestock-health-mvp
```

## 3. Backend (Flask API) — terminal 1

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
python -m server.app
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m server.app
```

You should see `Running on http://127.0.0.1:5000`. The first start creates and seeds
`data/surveillance.db` (takes a few seconds). Quick check in a browser:
http://localhost:5000/api/v1/health → `{"status":"ok","cases":150,...}`

## 4. Frontend (React / Vite) — terminal 2

```bash
cd client
npm install
npm run dev
```

Open **http://localhost:5173** and log in with any demo account (password `1234`):
`farmer1`, `paravet1`, `ldo1`, `acah1`, `dcah1`, `state1`, `lab1`, `admin`.
The dev server proxies `/api` and `/webhooks` to the Flask API on port 5000, so both
terminals must stay open.

## Coming back later

Each time you open a new terminal:

```bash
# terminal 1
.\.venv\Scripts\Activate.ps1      # Windows   |   source .venv/bin/activate  (macOS/Linux)
python -m server.app

# terminal 2
cd client && npm run dev
```

Pull the latest code with `git pull` (re-run `pip install -r requirements.txt` / `npm install`
only if `requirements.txt` or `client/package.json` changed).

## Alternatives

**Single-process demo (one terminal, port 5000).** Build the SPA once and let Flask serve it:
```bash
cd client && npm run build && cd ..
python -m server.app            # → http://localhost:5000 serves UI + API
```

**Show it to teammates without installing anything.** Both servers bind to `0.0.0.0`, so
anyone on the same Wi-Fi can open `http://<your-LAN-IP>:5173` (find your IP with
`ipconfig` on Windows or `ifconfig` / `ip a` on macOS/Linux). Allow Python/Node through
the firewall if prompted.

## Troubleshooting

| Problem | Fix |
|---|---|
| `externally-managed-environment` from pip | You skipped the venv step — create/activate `.venv` first. |
| `'python' is not recognized` (Windows) | Reinstall Python with "Add to PATH", or use `py -m venv .venv`. |
| `Activate.ps1 cannot be loaded` (Windows) | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry. |
| `npm run dev` fails with a Node version error | Vite 7 needs Node 20.19+ / 22.12+ — install Node 22 LTS. |
| Port 5000 already in use (macOS AirPlay Receiver uses it) | `PORT=5001 python -m server.app` and change both targets in `client/vite.config.js` to `:5001`. |
| UI loads but every page shows API errors | The Flask terminal is not running, or it crashed — check terminal 1. |
| Want fresh demo data | Stop the API, delete the `data/` folder, start it again. |

## Optional environment variables

| Variable | Purpose | Default |
|---|---|---|
| `PORT` | API port | `5000` |
| `SECRET_KEY` | JWT / barcode signing secret | dev value (fine for local) |
| `DB_PATH` | SQLite file location | `data/surveillance.db` |
| `DATABASE_URL` | PostGIS backend for nearest-clinic queries | unset → Haversine |
| `FLASK_DEBUG=1` | Auto-reload the API on code changes | off |

## Contributing changes

The repo is public, so cloning needs no permissions. To **push** changes the owner must add
you as a collaborator (GitHub → repo → Settings → Collaborators). Work on a branch and open
a pull request:

```bash
git checkout -b feature/my-change
git add -A && git commit -m "Describe the change"
git push -u origin feature/my-change
```

# Nannagaru Medicine Assistant (NaaPills)

A simple, elderly-friendly medicine reminder web app for THR (Total Hip Replacement) recovery. Built for **Nannagaru** with large text, minimal clicks, and a calm retro hospital-chart feel.

## Features

- **Home screen** with four large period buttons: Morning, Afternoon, Evening, Bed Time
- **Medication cards** showing image, name, dose, food instructions, time, and notes
- **Daily tracking** — mark each dose as taken with one tap
- **Progress bar** — today's completion (e.g. 7 / 14 Medicines Taken)
- **JSON storage** — no database required

## Tech Stack

| Layer    | Technology              |
|----------|-------------------------|
| Backend  | Python, FastAPI         |
| Frontend | HTML, CSS, Bootstrap 5, AngularJS 1.x, jQuery |
| Storage  | JSON files              |
| Deploy   | Vercel (static + serverless API) |

## Project Structure

```
NaaPills/
├── api/
│   └── index.py              # Vercel serverless entry
├── backend/
│   ├── main.py               # FastAPI app
│   ├── data/
│   │   ├── medicines.json    # All dose schedules
│   │   └── tracking.json     # Daily completion log
│   └── services/
│       ├── data_loader.py
│       ├── medicine_service.py
│       └── tracking_service.py
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   ├── templates/
│   └── images/
├── data/                     # Original prescription source data
├── vercel.json
└── requirements.txt
```

## Local Development

### 1. Install dependencies

```bash
# Using uv (recommended)
uv sync
uv pip install -r requirements.txt

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

The FastAPI app serves both the API (`/api/*`) and the static frontend.

### 3. API Endpoints

| Method | Endpoint                  | Description                          |
|--------|---------------------------|--------------------------------------|
| GET    | `/api/medicines`          | All active doses for today           |
| GET    | `/api/medicines/{period}` | Doses for morning/afternoon/evening/bedtime |
| GET    | `/api/today`              | Medicines grouped by period          |
| GET    | `/api/status/today`       | Today's progress and dose status     |
| GET    | `/api/pilltrack`          | Caregiver daily intake report        |
| POST   | `/api/mark-taken`         | Mark a dose taken or undo            |

**Mark taken example:**

```bash
curl -X POST http://localhost:8000/api/mark-taken \
  -H "Content-Type: application/json" \
  -d '{"dose_id": "dolo_650_morning", "taken": true}'
```

## Deploy to Vercel

### 1. Push to GitHub

```bash
git add .
git commit -m "Ready for deployment"
git push origin main
```

### 2. Deploy

**Option A — Vercel Dashboard:** Import the repo at [vercel.com/new](https://vercel.com/new). No extra config needed.

**Option B — CLI:**

```bash
npm i -g vercel   # if not installed
vercel --prod
```

### 3. What gets deployed

| URL | Purpose |
|-----|---------|
| `/` | Main app for Nannagaru |
| `/pilltrack` | Caregiver dashboard (not linked from main app) |
| `/api/*` | FastAPI backend |

### 4. Enable permanent tracking (free — one-time setup)

Tracking data must persist in the cloud. On the **Hobby (free) plan**, use Vercel Blob:

1. Open your project on [vercel.com](https://vercel.com)
2. Go to **Storage** tab → **Create Database** → choose **Blob**
3. Name it `naapills-tracking` → **Connect to Project** → select `naapills`
4. Vercel auto-adds `BLOB_READ_WRITE_TOKEN` to your project
5. **Redeploy** (Deployments → ⋯ → Redeploy)

That's it. Tracking JSON is stored permanently at `naapills/tracking.json` in Blob.
Free Hobby limits: 1 GB storage, 10k operations/month — more than enough for this app.

### 5. After deploy

- Open the main URL on Nannagaru's phone and **Add to Home Screen**
- Bookmark `/pilltrack` on your phone to monitor daily intake

### Notes

- **With Blob store:** tracking persists permanently in the cloud
- **Without Blob store:** tracking uses temporary `/tmp` on Vercel and may reset
- Tracking is **not** stored on Nannagaru's phone — it's server-side only
- Medicine images are in `frontend/images/` — case-sensitive on Vercel (Linux)

## Medicine Schedule (from discharge prescription)

| Medicine           | Times                              | Duration |
|--------------------|------------------------------------|----------|
| Panhorst DSR 40mg  | 07:30 AM (before breakfast)        | 15 days  |
| Dolo 650           | 08:00 AM, 02:00 PM, 08:00 PM       | 15 days  |
| Zyapixa 2.5mg      | 09:00 AM, 09:00 PM                 | 30 days  |
| Steon K2           | 09:00 AM, 09:00 PM                 | 60 days  |
| Build Joint Tablet | 09:00 AM, 09:00 PM                 | 60 days  |
| Ticobon-MR         | 10:00 AM, 10:00 PM                 | 15 days  |
| Health-3R Vanilla  | 11:00 AM (2 tsp in warm milk)      | 60 days  |
| Pregcoba-NT        | 09:00 PM (bedtime)                 | 30 days  |

**Total: 14 doses per day**

## Adding Medicine Photos

Place images in `frontend/images/` (current filenames):

- `panthorst.jpg`
- `dolo650.png`
- `zyapixa.PNG`
- `steonk2.PNG`
- `build-joint.PNG`
- `ticobon-mr.jpg`
- `pregcoba.PNG`
- `placeholder.svg` (fallback for Health-3R)

A pill placeholder SVG is included (`placeholder.svg`) and shown automatically when an image is missing.

## Future Extensions (not implemented)

Architecture supports adding later:

- Push notifications
- Voice reminders
- Multiple prescription sets
- Caregiver dashboard
- Multiple patients

## License

Private family use — Nannagaru THR Recovery 2026.

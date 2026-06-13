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
| POST   | `/api/mark-taken`         | Mark a dose taken or undo            |

**Mark taken example:**

```bash
curl -X POST http://localhost:8000/api/mark-taken \
  -H "Content-Type: application/json" \
  -d '{"dose_id": "dolo_650_morning", "taken": true}'
```

## Deploy to Vercel

1. Install the [Vercel CLI](https://vercel.com/docs/cli)
2. From the project root:

```bash
vercel
```

3. Vercel serves:
   - **Frontend** as static files from `frontend/`
   - **API** as serverless Python from `api/index.py`

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

Place JPG/PNG images in `frontend/images/` matching the filenames in `medicines.json`:

- `panhorst-dsr.jpg`
- `dolo-650.jpg`
- `zyapixa.jpg`
- `steon-k2.jpg`
- `build-joint.jpg`
- `ticobon-mr.jpg`
- `health-3r.jpg`
- `pregcoba-nt.jpg`

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

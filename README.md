# AI Guardian 🛡️

An AI-powered smart home security platform that transforms traditional CCTV systems into intelligent surveillance solutions.

## What it does

AI Guardian connects to existing CCTV cameras and uses real-time computer vision and AI to detect suspicious activities around residential or commercial premises. Instead of recording everything and making you review hours of footage, it only alerts you when something actually suspicious happens.

**Detects:**
- 🚪 Unauthorized access beyond restricted zones
- 🚮 Garbage dumping near property boundary
- 🧍 Suspicious loitering near gates (>30 seconds)
- 🚗 Vehicles parked suspiciously
- 🐕 Stray animals entering property
- 🌙 After-hours activity in shop/premises

**When detected, instantly sends:**
- 📸 Annotated photo with bounding boxes
- 🎥 15-second video clip
- 📍 Camera name + timestamp
- 🤖 AI-generated description of what happened
- ⚡ Severity level (Low / Medium / High)

## What makes it different from standard CCTV systems

| Feature | Standard CCTV | AI Guardian |
|---------|--------------|-------------|
| Alerts | Motion only | Behavior-aware |
| False alerts | Constant | Near zero |
| Evidence | Raw footage | Annotated photo + video |
| Search | Manual scrubbing | Natural language AI search |
| Notifications | Proprietary app | WhatsApp / Telegram |
| Setup cost | ₹50,000+ | Open source |
| Family alerts | Not included | Multiple recipients |
| AI description | None | "Person loitering 35s near gate" |

## Architecture

6 CCTV Cameras (RTSP/RTSPS)
↓
ffmpeg frame capture
↓
YOLOv8n — person, vehicle, animal detection
↓
Zone-based filtering — only alert in defined zones
↓
Groq Vision (qwen3.6-27b) — verify if truly suspicious
↓
FastAPI backend — store incidents
↓
Telegram alerts — photo + video + AI description
↓
React dashboard — live feeds, incidents, AI search


## Tech Stack

- **Computer Vision:** YOLOv8 (Ultralytics)
- **AI Verification:** Groq Vision (qwen/qwen3.6-27b)
- **Backend:** FastAPI + Python
- **Frontend:** React + Vite + Recharts
- **Alerts:** Telegram Bot API
- **Camera Protocol:** RTSPS (CP Plus DVR)
- **Storage:** Cloudinary (images/videos)

## Features

### Smart Zone Detection
Define custom zones on each camera. Only alert when someone enters restricted areas — not for every person walking by.

### Groq Vision Verification
Every detection is verified by Groq Vision AI before sending alert. Eliminates false positives — your family member sitting in shop won't trigger alerts.

### Natural Language Search
Search incidents using plain English:
- "Show all people near gate after 10 PM"
- "Vehicles detected this week"
- "All loitering incidents today"

### Multi-recipient Alerts
Send alerts to entire family group on Telegram — works internationally.

### Daily Reports
Automated daily security summary with incident counts by camera and severity.

## Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- ffmpeg installed
- CP Plus / Hikvision / Dahua DVR with RTSP enabled
- Telegram Bot (free)
- Groq API key (free tier available)

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Add your API keys
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

DVR_IP=192.168.1.x
DVR_USER=admin
DVR_PASSWORD=your_password

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_group_chat_id

GROQ_API_KEY=your_groq_key

CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret


### Camera RTSP URL Format (CP Plus)

rtsps://admin:password@DVR_IP:554/cam/realmonitor?channel=1&subtype=0


## Dashboard

- **Dashboard** — Stats, charts, recent incidents
- **Live Cameras** — Snapshot from each camera on demand
- **Incidents** — Full incident history with photos, filters, download
- **AI Search** — Natural language search across all incidents

## 24/7 Operation

```bash
bash keep_running.sh
```

Auto-restarts if backend crashes. Keep terminal open or run as a service.

## Resume Bullets

- Built AI-powered CCTV security system using YOLOv8 + Groq Vision to detect suspicious behavior (loitering, garbage dumping, unauthorized access) with near-zero false positives
- Implemented zone-based detection with Groq Vision verification — system ignores normal activity and only alerts on genuinely suspicious events
- Integrated Telegram Bot for real-time family alerts with annotated photos, video clips, and AI-generated incident descriptions
- Built React dashboard with natural language incident search, live camera snapshots, incident history, and analytics

## License
MIT

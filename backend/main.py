"""
AI Guardian - FastAPI Backend
Serves dashboard, manages incidents, runs detection
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import threading
from dotenv import load_dotenv

load_dotenv()

from smart_detector import SmartGuardian, CAMERA_ZONES, capture_frame, IMAGES_DIR, VIDEOS_DIR
CAMERAS = {k: {"name": v["name"]} for k, v in CAMERA_ZONES.items()}
from telegram_alerts import send_telegram_alert, send_daily_report

app = FastAPI(title="AI Guardian API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve captured images and videos
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CAPTURES_DIR = os.path.join(BASE_DIR, "captures")
app.mount("/captures", StaticFiles(directory=CAPTURES_DIR), name="captures")

# Global guardian instance
guardian = SmartGuardian()
guardian.add_alert_callback(send_telegram_alert)

monitoring_thread = None


@app.get("/")
def root():
    return {"status": "AI Guardian running", "cameras": len(CAMERAS)}


@app.get("/cameras")
def get_cameras():
    return {"cameras": [
        {"id": k, "name": v["name"]} for k, v in CAMERAS.items()
    ]}


@app.get("/cameras/{cam_id}/snapshot")
def get_snapshot(cam_id: int):
    """Get latest snapshot from camera"""
    import numpy as np
    import cv2
    import tempfile

    frame = capture_frame(cam_id)
    if frame is None:
        return {"error": "Could not capture frame"}
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"snapshot_cam{cam_id}_{timestamp}.jpg"
    filepath = os.path.join(IMAGES_DIR, filename)
    cv2.imwrite(filepath, frame)
    
    return {"image": filename, "url": f"/captures/images/{filename}"}


@app.get("/incidents")
def get_incidents(
    cam_id: Optional[int] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get incidents with optional filters"""
    incidents = guardian.incidents
    
    if cam_id:
        incidents = [i for i in incidents if i.get("cam_id") == cam_id]
    if severity:
        incidents = [i for i in incidents if i.get("severity") == severity]
    
    # Sort by timestamp descending
    incidents = sorted(incidents, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    return {
        "total": len(incidents),
        "incidents": incidents[offset:offset+limit],
    }


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    """Get single incident by ID"""
    for inc in guardian.incidents:
        if inc.get("id") == incident_id:
            return inc
    return {"error": "Incident not found"}


@app.delete("/incidents/{incident_id}")
def delete_incident(incident_id: str):
    """Delete an incident"""
    guardian.incidents = [i for i in guardian.incidents if i.get("id") != incident_id]
    from detector import save_incidents
    save_incidents(guardian.incidents)
    return {"success": True}


class SearchQuery(BaseModel):
    query: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@app.post("/incidents/search")
def search_incidents(payload: SearchQuery):
    """AI-powered natural language search"""
    from groq import Groq
    import os

    incidents = guardian.incidents

    # Filter by date if provided
    if payload.start_date:
        incidents = [i for i in incidents 
                    if i.get("timestamp", "") >= payload.start_date]
    if payload.end_date:
        incidents = [i for i in incidents 
                    if i.get("timestamp", "") <= payload.end_date]

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Build context for AI
        incident_summary = json.dumps([{
            "id": i["id"],
            "time": i["timestamp"],
            "camera": i["cam_name"],
            "severity": i["severity_label"],
            "detections": [d["class"] for d in i["detections"]],
        } for i in incidents[-100:]], indent=2)  # last 100 incidents

        prompt = f"""You are searching security incidents. 
User query: "{payload.query}"

Available incidents:
{incident_summary}

Return a JSON array of incident IDs that match the query.
Example: ["INC_20240101_120000_CAM1", "INC_20240101_130000_CAM2"]
Return ONLY the JSON array, nothing else."""

        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )

        import re
        text = response.choices[0].message.content.strip()
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            ids = json.loads(match.group())
            results = [i for i in incidents if i.get("id") in ids]
            return {"results": results, "query": payload.query}

    except Exception as e:
        print(f"Search error: {e}")

    # Fallback — keyword search
    query_lower = payload.query.lower()
    results = [i for i in incidents if
               query_lower in i.get("cam_name", "").lower() or
               query_lower in i.get("severity_label", "").lower() or
               any(query_lower in d.get("class", "") for d in i.get("detections", []))]

    return {"results": results, "query": payload.query}


@app.get("/stats")
def get_stats():
    """Get dashboard statistics"""
    incidents = guardian.incidents
    today = datetime.now().date()
    
    today_incidents = [i for i in incidents 
                      if datetime.fromisoformat(i["timestamp"]).date() == today]
    
    by_camera = {}
    by_severity = {}
    
    for inc in incidents:
        cam = inc.get("cam_name", "Unknown")
        sev = inc.get("severity", "normal")
        by_camera[cam] = by_camera.get(cam, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1
    
    return {
        "total_incidents": len(incidents),
        "today_incidents": len(today_incidents),
        "cameras_active": len(CAMERAS),
        "by_camera": by_camera,
        "by_severity": by_severity,
        "monitoring": guardian.running,
    }


@app.post("/monitoring/start")
def start_monitoring():
    """Start AI monitoring"""
    global monitoring_thread
    if not guardian.running:
        monitoring_thread = threading.Thread(
            target=guardian.start, daemon=True
        )
        monitoring_thread.start()
        return {"status": "Monitoring started"}
    return {"status": "Already monitoring"}


@app.post("/monitoring/stop")
def stop_monitoring():
    """Stop AI monitoring"""
    guardian.stop()
    return {"status": "Monitoring stopped"}


@app.post("/report/daily")
def trigger_daily_report():
    """Send daily report manually"""
    today = datetime.now().date()
    today_incidents = [i for i in guardian.incidents 
                      if datetime.fromisoformat(i["timestamp"]).date() == today]
    send_daily_report(today_incidents)
    return {"status": "Report sent", "incidents": len(today_incidents)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

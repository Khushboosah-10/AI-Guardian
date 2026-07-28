"""
AI Guardian - Smart CCTV Detection Engine
Detects: garbage dumping, loitering, vandalism, vehicles, animals
"""

import cv2
import subprocess
import numpy as np
import time
import os
import json
from datetime import datetime
from ultralytics import YOLO
import threading
from collections import defaultdict

# ── Camera Config ─────────────────────────────────────────────────────────────
DVR_IP = os.getenv("DVR_IP", "192.168.1.6")
DVR_USER = os.getenv("DVR_USER", "admin")
DVR_PASS = os.getenv("DVR_PASSWORD", "194rit%4008")

CAMERAS = {
    1: {"name": "Shop",                      "url": f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel=1&subtype=0"},
    2: {"name": "Street Left (Entrance Gate)","url": f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel=2&subtype=0"},
    3: {"name": "Camera 3",                  "url": f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel=3&subtype=0"},
    4: {"name": "Street Right (Shop Gate)",  "url": f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel=4&subtype=0"},
    5: {"name": "Parking",                   "url": f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel=5&subtype=0"},
    6: {"name": "Street Left (Shop Gate)",   "url": f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel=6&subtype=0"},
    7: {"name": "Camera 7",                  "url": f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel=7&subtype=0"},
    8: {"name": "Street Right (Entrance Gate)","url": f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel=8&subtype=0"},
}

# ── Directories ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "captures/images")
VIDEOS_DIR = os.path.join(BASE_DIR, "captures/videos")
INCIDENTS_FILE = os.path.join(BASE_DIR, "captures/incidents.json")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)

# ── Detection Config ──────────────────────────────────────────────────────────
FRAME_WIDTH = 960
FRAME_HEIGHT = 1080
CONFIDENCE_THRESHOLD = 0.25
LOITER_THRESHOLD = 15       # seconds before loitering alert
VIDEO_DURATION = 15         # seconds of video to record
SCAN_INTERVAL = 3           # seconds between scans

# ── Severity Levels ───────────────────────────────────────────────────────────
SEVERITY = {
    "normal":    {"emoji": "🟢", "label": "Normal Activity",    "level": 1},
    "loitering": {"emoji": "🟡", "label": "Suspicious Loitering","level": 2},
    "garbage":   {"emoji": "🟠", "label": "Garbage Dumping",    "level": 3},
    "vandalism": {"emoji": "🔴", "label": "Vandalism / Damage", "level": 4},
    "vehicle":   {"emoji": "🟠", "label": "Vehicle Incident",   "level": 3},
    "animal":    {"emoji": "🟡", "label": "Stray Animal",       "level": 2},
    "person":    {"emoji": "🟡", "label": "Person Detected",    "level": 2},
}

# ── YOLO class → event type mapping ──────────────────────────────────────────
CLASS_TO_EVENT = {
    "person":     "person",
    "car":        "vehicle",
    "truck":      "vehicle",
    "motorcycle": "vehicle",
    "bus":        "vehicle",
    "dog":        "animal",
    "cat":        "animal",
    "cow":        "animal",
    "horse":      "animal",
    "backpack":   "person",
    "handbag":    "person",
    "suitcase":   "person",
    "bottle":     "garbage",
    "cup":        "garbage",
    "banana":     "garbage",
    "apple":      "garbage",
    "scissors":   "vandalism",
    "knife":      "vandalism",
}


def capture_frame(cam_id):
    """Capture a single frame from camera using ffmpeg"""
    url = CAMERAS[cam_id]["url"]
    command = [
        'ffmpeg', '-rtsp_transport', 'tcp',
        '-i', url, '-vframes', '1',
        '-f', 'image2pipe', '-pix_fmt', 'bgr24',
        '-vcodec', 'rawvideo', '-'
    ]
    try:
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw = pipe.stdout.read(FRAME_WIDTH * FRAME_HEIGHT * 3)
        pipe.terminate()
        if len(raw) == FRAME_WIDTH * FRAME_HEIGHT * 3:
            return np.frombuffer(raw, dtype=np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
    except Exception as e:
        print(f"CAM{cam_id} capture error: {e}")
    return None


def record_video_clip(cam_id, duration=VIDEO_DURATION):
    """Record a video clip from camera"""
    url = CAMERAS[cam_id]["url"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"clip_cam{cam_id}_{timestamp}.mp4"
    filepath = os.path.join(VIDEOS_DIR, filename)

    command = [
        'ffmpeg', '-rtsp_transport', 'tcp',
        '-i', url,
        '-t', str(duration),
        '-c:v', 'libx264', '-preset', 'fast',
        '-crf', '28', '-y', filepath
    ]

    try:
        subprocess.run(command, capture_output=True, timeout=duration + 10)
        if os.path.exists(filepath):
            return filename
    except Exception as e:
        print(f"Video recording error: {e}")
    return None


def save_incidents(incidents):
    """Save incidents to JSON file"""
    with open(INCIDENTS_FILE, "w") as f:
        json.dump(incidents, f, indent=2, default=str)


def load_incidents():
    """Load incidents from JSON file"""
    if os.path.exists(INCIDENTS_FILE):
        with open(INCIDENTS_FILE, "r") as f:
            return json.load(f)
    return []


class AIGuardian:
    def __init__(self):
        print("🤖 Loading YOLOv8 model...")
        self.model = YOLO("yolov8n.pt")
        print("✅ YOLOv8 loaded!")

        self.incidents = load_incidents()
        self.person_tracker = defaultdict(float)  # cam_id -> first_seen_time
        self.alert_callbacks = []
        self.running = False
        self.last_alert_time = defaultdict(float)  # prevent spam alerts
        self.alert_cooldown = 60  # seconds between alerts per camera

    def add_alert_callback(self, callback):
        self.alert_callbacks.append(callback)

    def detect(self, frame, cam_id):
        """Run YOLOv8 on frame and return detections"""
        results = self.model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
        detections = []

        for r in results:
            for box in r.boxes:
                cls_name = self.model.names[int(box.cls[0])]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                event_type = CLASS_TO_EVENT.get(cls_name, None)

                if event_type:
                    detections.append({
                        "class": cls_name,
                        "event_type": event_type,
                        "confidence": round(conf, 2),
                        "bbox": [x1, y1, x2, y2],
                    })

        return detections

    def analyze_behavior(self, detections, cam_id):
        """Analyze detections for suspicious behavior patterns"""
        now = time.time()
        events = []

        has_person = any(d["event_type"] == "person" for d in detections)

        if has_person:
            if self.person_tracker[cam_id] == 0:
                self.person_tracker[cam_id] = now
            else:
                duration = now - self.person_tracker[cam_id]
                if duration > LOITER_THRESHOLD:
                    events.append({
                        "type": "loitering",
                        "duration": int(duration),
                        "message": f"Person loitering for {int(duration)} seconds",
                    })
        else:
            self.person_tracker[cam_id] = 0

        # Check for garbage
        garbage_items = [d for d in detections if d["event_type"] == "garbage"]
        if garbage_items and has_person:
            events.append({
                "type": "garbage",
                "message": "Person near garbage/waste items",
            })

        # Check for vehicles
        vehicles = [d for d in detections if d["event_type"] == "vehicle"]
        if vehicles:
            events.append({
                "type": "vehicle",
                "message": f"Vehicle detected: {vehicles[0]['class']}",
            })

        # Check for animals
        animals = [d for d in detections if d["event_type"] == "animal"]
        if animals:
            events.append({
                "type": "animal",
                "message": f"Stray animal detected: {animals[0]['class']}",
            })

        return events

    def create_incident(self, frame, cam_id, detections, events):
        """Create incident record with annotated image"""
        timestamp = datetime.now()
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")

        # Determine severity
        if events:
            severity_type = max(events, key=lambda e: SEVERITY.get(e["type"], SEVERITY["normal"])["level"])["type"]
        elif detections:
            severity_type = detections[0]["event_type"]
        else:
            severity_type = "normal"

        severity_info = SEVERITY.get(severity_type, SEVERITY["normal"])

        # Draw bounding boxes on frame
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            color = (0, 255, 0) if det["event_type"] == "person" else (0, 165, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"{det['class']} {det['confidence']:.0%}"
            cv2.putText(annotated, label, (x1, max(y1-10, 20)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Add info overlay
        cam_name = CAMERAS[cam_id]["name"]
        cv2.putText(annotated, f"AI Guardian | {cam_name}",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
        cv2.putText(annotated, timestamp.strftime("%d/%m/%Y %I:%M:%S %p"),
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if events:
            cv2.putText(annotated, f"{severity_info['emoji']} {severity_info['label']}",
                       (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Save image
        image_filename = f"incident_cam{cam_id}_{ts_str}.jpg"
        image_path = os.path.join(IMAGES_DIR, image_filename)
        cv2.imwrite(image_path, annotated)

        incident = {
            "id": f"INC_{ts_str}_CAM{cam_id}",
            "timestamp": timestamp.isoformat(),
            "cam_id": cam_id,
            "cam_name": cam_name,
            "detections": detections,
            "events": events,
            "severity": severity_type,
            "severity_label": severity_info["label"],
            "severity_emoji": severity_info["emoji"],
            "image": image_filename,
            "video": None,
        }

        self.incidents.append(incident)
        save_incidents(self.incidents)

        return incident, image_path

    def trigger_alerts(self, incident, image_path):
        """Trigger all registered alert callbacks"""
        for callback in self.alert_callbacks:
            try:
                callback(incident, image_path)
            except Exception as e:
                print(f"Alert callback error: {e}")

    def should_alert(self, cam_id):
        """Check if enough time has passed since last alert"""
        now = time.time()
        if now - self.last_alert_time[cam_id] > self.alert_cooldown:
            self.last_alert_time[cam_id] = now
            return True
        return False

    def process_camera(self, cam_id):
        """Process single camera — capture, detect, analyze, alert"""
        frame = capture_frame(cam_id)
        if frame is None:
            return None

        detections = self.detect(frame, cam_id)
        if not detections:
            return None

        events = self.analyze_behavior(detections, cam_id)
        incident, image_path = self.create_incident(frame, cam_id, detections, events)

        # Only alert if cooldown passed and events detected
        if events and self.should_alert(cam_id):
            # Record video clip in background
            def record_and_alert():
                print(f"🎥 Recording video clip for CAM{cam_id}...")
                video_file = record_video_clip(cam_id)
                if video_file:
                    incident["video"] = video_file
                    save_incidents(self.incidents)
                self.trigger_alerts(incident, image_path)

            threading.Thread(target=record_and_alert, daemon=True).start()

        print(f"{'🚨' if events else '👁'} CAM{cam_id} ({CAMERAS[cam_id]['name']}): "
              f"{[d['class'] for d in detections]} | "
              f"{[e['type'] for e in events] if events else 'monitoring'}")

        return incident

    def start(self, cam_ids=None):
        if cam_ids is None:
          cam_ids = list(CAMERAS.keys())  # all 8 cameras

        self.running = True
        print(f"\n🛡️  AI Guardian started — monitoring cameras: {cam_ids}")
        print(f"📁 Saving to: {IMAGES_DIR}")
        print(f"⏱️  Scan interval: {SCAN_INTERVAL}s\n")

        while self.running:
            for cam_id in cam_ids:
                try:
                    self.process_camera(cam_id)
                except Exception as e:
                    print(f"Error on CAM{cam_id}: {e}")
            time.sleep(SCAN_INTERVAL)

    def stop(self):
        self.running = False
        print("AI Guardian stopped.")


if __name__ == "__main__":
    guardian = AIGuardian()
    print("Testing detection on all cameras...")
    for cam_id in [1, 2, 3, 5, 6]:
        incident = guardian.process_camera(cam_id)
        if incident:
            print(f"  Incident: {incident['severity_emoji']} {incident['severity_label']}")

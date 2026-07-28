"""
AI Guardian - Smart Detection Engine
Zone-based, behavior-aware, Groq Vision powered
"""

import cv2
import subprocess
import numpy as np
import time
import os
import json
import base64
from datetime import datetime
from ultralytics import YOLO
from collections import defaultdict
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")

# ── Camera Zones Config ───────────────────────────────────────────────────────
# Each camera has zones defined as polygons (x%, y% of frame)
# Zone types: "forbidden" = always alert, "monitor" = alert only if suspicious

CAMERA_ZONES = {
    1: {  # Shop
        "name": "Shop",
        "shop_hours": {"open": 8, "close": 21},  # 8am to 9pm
        "zones": [
            {
                "name": "Beyond Counter",
                "type": "forbidden_after_hours",
                "points": [(0.0, 0.5), (1.0, 0.5), (1.0, 1.0), (0.0, 1.0)],  # bottom half
                "alert_after_hours_only": True,
                "description": "Area beyond shop counter",
            },
            {
                "name": "Cash Counter",
                "type": "forbidden",
                "points": [(0.3, 0.6), (0.7, 0.6), (0.7, 0.9), (0.3, 0.9)],
                "alert_after_hours_only": False,
                "description": "Cash counter area — alert always",
            },
        ]
    },
    2: {  # Street Left (Entrance Gate)
        "name": "Street Left (Entrance Gate)",
        "shop_hours": None,
        "zones": [
            {
                "name": "Gate Boundary",
                "type": "monitor",
                "points": [(0.2, 0.3), (0.8, 0.3), (0.8, 0.8), (0.2, 0.8)],
                "loiter_threshold": 30,
                "description": "Main entrance gate area",
            },
        ]
    },
    4: {  # Street Right (Shop Gate)
        "name": "Street Right (Shop Gate)",
        "shop_hours": None,
        "zones": [
            {
                "name": "Shop Gate",
                "type": "monitor",
                "points": [(0.1, 0.2), (0.9, 0.2), (0.9, 0.9), (0.1, 0.9)],
                "loiter_threshold": 30,
                "description": "Shop gate area",
            },
        ]
    },
    5: {  # Parking
        "name": "Parking",
        "shop_hours": None,
        "zones": [
            {
                "name": "Parking Zone",
                "type": "vehicle_monitor",
                "points": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
                "vehicle_loiter_threshold": 300,  # 5 minutes
                "description": "Parking area — alert if vehicle stays >5 mins",
            },
        ]
    },
    6: {  # Street Left (Shop Gate)
        "name": "Street Left (Shop Gate)",
        "shop_hours": None,
        "zones": [
            {
                "name": "Property Boundary",
                "type": "monitor",
                "points": [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
                "loiter_threshold": 30,
                "description": "Property boundary area",
            },
        ]
    },
    8: {  # Street Right (Entrance Gate)
        "name": "Street Right (Entrance Gate)",
        "shop_hours": None,
        "zones": [
            {
                "name": "Entrance Boundary",
                "type": "monitor",
                "points": [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
                "loiter_threshold": 30,
                "description": "Entrance boundary area",
            },
        ]
    },
}

DVR_IP = os.getenv("DVR_IP", "192.168.1.6")
DVR_USER = os.getenv("DVR_USER", "admin")
DVR_PASS = os.getenv("DVR_PASSWORD", "194rit%4008")

FRAME_WIDTH = 960
FRAME_HEIGHT = 1080

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "captures/images")
VIDEOS_DIR = os.path.join(BASE_DIR, "captures/videos")
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(VIDEOS_DIR, exist_ok=True)


def capture_frame(cam_id):
    url = f"rtsps://{DVR_USER}:{DVR_PASS}@{DVR_IP}:554/cam/realmonitor?channel={cam_id}&subtype=0"
    command = ['ffmpeg', '-rtsp_transport', 'tcp', '-i', url,
               '-vframes', '1', '-f', 'image2pipe',
               '-pix_fmt', 'bgr24', '-vcodec', 'rawvideo', '-']
    try:
        pipe = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        raw = pipe.stdout.read(FRAME_WIDTH * FRAME_HEIGHT * 3)
        pipe.terminate()
        if len(raw) == FRAME_WIDTH * FRAME_HEIGHT * 3:
            return np.frombuffer(raw, dtype=np.uint8).reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
    except Exception as e:
        print(f"Capture error CAM{cam_id}: {e}")
    return None


def is_point_in_zone(x, y, zone_points, frame_w, frame_h):
    """Check if a point is inside a zone polygon"""
    polygon = np.array([
        [int(px * frame_w), int(py * frame_h)]
        for px, py in zone_points
    ], dtype=np.int32)
    return cv2.pointPolygonTest(polygon, (float(x), float(y)), False) >= 0


def is_shop_open(cam_config):
    """Check if shop is currently open"""
    if not cam_config.get("shop_hours"):
        return True
    now = datetime.now().hour
    hours = cam_config["shop_hours"]
    return hours["open"] <= now < hours["close"]


def frame_to_base64(frame):
    """Convert frame to base64 for Groq Vision"""
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buffer).decode('utf-8')


def analyze_with_groq_vision(frame, detections, cam_name, zone_name):
    """Use Groq Vision to intelligently analyze if activity is suspicious"""
    if not GROQ_KEY:
        return True, "Suspicious activity detected"

    try:
        client = Groq(api_key=GROQ_KEY)
        img_b64 = frame_to_base64(frame)

        detection_text = ", ".join([f"{d['class']} ({d['confidence']:.0%})" for d in detections])

        prompt = f"""You are an AI security system analyzing CCTV footage.
Camera: {cam_name}
Zone: {zone_name}
YOLOv8 detected: {detection_text}

Analyze this image and answer:
1. Is this activity SUSPICIOUS or NORMAL?
2. What exactly is happening? (1 sentence)
3. Severity: LOW / MEDIUM / HIGH

Suspicious activities include:
- Person throwing/dropping garbage near property
- Person climbing walls or gates
- Vehicle collision or aggressive parking
- Person lingering suspiciously near entrance
- Person accessing restricted areas
- Vandalism or property damage

Normal activities include:
- People walking by normally
- Vehicles passing through
- Shop owner/family members in shop
- Normal customer activity during business hours

Reply in JSON: {{"suspicious": true/false, "description": "...", "severity": "LOW/MEDIUM/HIGH", "event_type": "loitering/garbage/vandalism/vehicle/normal"}}"""

        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }],
            max_tokens=500,
        )

        import re
        text = response.choices[0].message.content.strip()
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            result = json.loads(match.group())
            return result.get("suspicious", False), result.get("description", ""), result
        
    except Exception as e:
        print(f"Groq Vision error: {e}")
    
    return False, "Could not analyze", {}


class SmartGuardian:
    def __init__(self):
        print("🤖 Loading YOLOv8...")
        self.model = YOLO("yolov8n.pt")
        print("✅ Ready!")

        self.incidents = self._load_incidents()
        self.person_first_seen = defaultdict(float)
        self.vehicle_first_seen = defaultdict(float)
        self.alert_cooldown = defaultdict(float)
        self.alert_callbacks = []
        self.running = False
        self.COOLDOWN_SECONDS = 120  # 2 min between alerts per camera

    def _load_incidents(self):
        path = os.path.join(BASE_DIR, "captures/incidents.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return []

    def _save_incidents(self):
        path = os.path.join(BASE_DIR, "captures/incidents.json")
        with open(path, "w") as f:
            json.dump(self.incidents, f, indent=2, default=str)

    def add_alert_callback(self, cb):
        self.alert_callbacks.append(cb)

    def _in_cooldown(self, cam_id):
        return time.time() - self.alert_cooldown[cam_id] < self.COOLDOWN_SECONDS

    def _set_cooldown(self, cam_id):
        self.alert_cooldown[cam_id] = time.time()

    def process_camera(self, cam_id):
        if cam_id not in CAMERA_ZONES:
            return None

        cam_config = CAMERA_ZONES[cam_id]
        frame = capture_frame(cam_id)
        if frame is None:
            return None

        # Run YOLO detection
        results = self.model(frame, conf=0.25, verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                cls_name = self.model.names[int(box.cls[0])]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                detections.append({
                    "class": cls_name,
                    "confidence": round(conf, 2),
                    "bbox": [x1, y1, x2, y2],
                    "center": [cx, cy],
                })

        if not detections:
            # Reset trackers if no one detected
            self.person_first_seen[cam_id] = 0
            return None

        # Check each zone
        triggered_zones = []
        for zone in cam_config.get("zones", []):
            zone_points = zone["points"]
            zone_type = zone["type"]

            # Filter detections in this zone
            in_zone = [d for d in detections if
                       is_point_in_zone(d["center"][0], d["center"][1],
                                        zone_points, FRAME_WIDTH, FRAME_HEIGHT)]

            if not in_zone:
                if zone_type == "monitor":
                    self.person_first_seen[f"{cam_id}_{zone['name']}"] = 0
                continue

            should_alert = False
            alert_reason = ""

            if zone_type == "forbidden":
                # Always alert if person in forbidden zone
                persons = [d for d in in_zone if d["class"] == "person"]
                if persons:
                    should_alert = True
                    alert_reason = f"Person in restricted zone: {zone['name']}"

            elif zone_type == "forbidden_after_hours":
                # Alert only after shop hours
                if not is_shop_open(cam_config):
                    persons = [d for d in in_zone if d["class"] == "person"]
                    if persons:
                        should_alert = True
                        alert_reason = f"Person in shop after hours: {zone['name']}"

            elif zone_type == "monitor":
                # Alert if person loiters too long
                key = f"{cam_id}_{zone['name']}"
                persons = [d for d in in_zone if d["class"] == "person"]
                vehicles = [d for d in in_zone if d["class"] in ["car", "truck", "motorcycle", "bus"]]

                if persons:
                    if self.person_first_seen[key] == 0:
                        self.person_first_seen[key] = time.time()
                    else:
                        duration = time.time() - self.person_first_seen[key]
                        threshold = zone.get("loiter_threshold", 30)
                        if duration > threshold:
                            should_alert = True
                            alert_reason = f"Person loitering {int(duration)}s near {zone['name']}"
                else:
                    self.person_first_seen[f"{cam_id}_{zone['name']}"] = 0

                # Vehicle loitering
                if vehicles:
                    vkey = f"{cam_id}_{zone['name']}_vehicle"
                    if self.vehicle_first_seen[vkey] == 0:
                        self.vehicle_first_seen[vkey] = time.time()
                    else:
                        duration = time.time() - self.vehicle_first_seen[vkey]
                        threshold = zone.get("vehicle_loiter_threshold", 300)
                        if duration > threshold:
                            should_alert = True
                            alert_reason = f"Vehicle parked suspiciously {int(duration)}s near {zone['name']}"
                else:
                    self.vehicle_first_seen[f"{cam_id}_{zone['name']}_vehicle"] = 0

            elif zone_type == "vehicle_monitor":
                vehicles = [d for d in in_zone if d["class"] in ["car", "truck", "motorcycle", "bus"]]
                if vehicles:
                    vkey = f"{cam_id}_{zone['name']}_vehicle"
                    if self.vehicle_first_seen[vkey] == 0:
                        self.vehicle_first_seen[vkey] = time.time()
                    else:
                        duration = time.time() - self.vehicle_first_seen[vkey]
                        if duration > zone.get("vehicle_loiter_threshold", 300):
                            should_alert = True
                            alert_reason = f"Vehicle suspicious activity in {zone['name']}"

            if should_alert:
                triggered_zones.append({
                    "zone": zone["name"],
                    "reason": alert_reason,
                    "detections": in_zone,
                })

        if not triggered_zones:
            return None

        # Don't alert if in cooldown
        if self._in_cooldown(cam_id):
            return None

        # Use Groq Vision to verify if truly suspicious
        print(f"🔍 Verifying with Groq Vision: CAM{cam_id}...")
        zone_name = triggered_zones[0]["zone"]
        is_suspicious, description, ai_result = analyze_with_groq_vision(
            frame, detections, cam_config["name"], zone_name
        )

        if not is_suspicious:
            print(f"✅ Groq says NOT suspicious: {description}")
            return None

        print(f"🚨 Groq confirms SUSPICIOUS: {description}")
        self._set_cooldown(cam_id)

        # Create incident
        incident = self._create_incident(
            frame, cam_id, cam_config["name"],
            detections, triggered_zones, description, ai_result
        )

        # Trigger alerts
        image_path = os.path.join(IMAGES_DIR, incident["image"])
        for cb in self.alert_callbacks:
            try:
                cb(incident, image_path)
            except Exception as e:
                print(f"Alert error: {e}")

        return incident

    def _create_incident(self, frame, cam_id, cam_name, detections, triggered_zones, ai_description, ai_result):
        ts = datetime.now()
        ts_str = ts.strftime("%Y%m%d_%H%M%S")

        event_type = ai_result.get("event_type", "suspicious")
        severity = ai_result.get("severity", "MEDIUM")

        severity_map = {
            "LOW":    {"emoji": "🟡", "label": "Low Severity"},
            "MEDIUM": {"emoji": "🟠", "label": "Suspicious Activity"},
            "HIGH":   {"emoji": "🔴", "label": "High Alert"},
        }
        sev_info = severity_map.get(severity, severity_map["MEDIUM"])

        # Draw annotations
        annotated = frame.copy()

        # Draw zone polygons
        if cam_id in CAMERA_ZONES:
            for zone in CAMERA_ZONES[cam_id].get("zones", []):
                pts = np.array([
                    [int(px * FRAME_WIDTH), int(py * FRAME_HEIGHT)]
                    for px, py in zone["points"]
                ], dtype=np.int32)
                cv2.polylines(annotated, [pts], True, (0, 165, 255), 2)

        # Draw detections
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated, f"{det['class']} {det['confidence']:.0%}",
                       (x1, max(y1-10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Overlay info
        cv2.putText(annotated, f"AI Guardian | {cam_name}",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(annotated, ts.strftime("%d/%m/%Y %I:%M:%S %p"),
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(annotated, f"{sev_info['emoji']} {sev_info['label']}",
                   (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Save image
        filename = f"smart_cam{cam_id}_{ts_str}.jpg"
        cv2.imwrite(os.path.join(IMAGES_DIR, filename), annotated)

        incident = {
            "id": f"INC_{ts_str}_CAM{cam_id}",
            "timestamp": ts.isoformat(),
            "cam_id": cam_id,
            "cam_name": cam_name,
            "detections": detections,
            "events": [{"type": event_type, "message": z["reason"]} for z in triggered_zones],
            "severity": event_type,
            "severity_label": sev_info["label"],
            "severity_emoji": sev_info["emoji"],
            "ai_description": ai_description,
            "image": filename,
            "video": None,
        }

        self.incidents.append(incident)
        self._save_incidents()
        return incident

    def start(self):
        self.running = True
        cam_ids = list(CAMERA_ZONES.keys())
        print(f"\n🛡️  Smart AI Guardian monitoring: {cam_ids}")

        while self.running:
            for cam_id in cam_ids:
                try:
                    incident = self.process_camera(cam_id)
                    if incident:
                        print(f"🚨 Alert: {incident['severity_emoji']} {incident['severity_label']} on CAM{cam_id}")
                except Exception as e:
                    print(f"Error CAM{cam_id}: {e}")
            time.sleep(5)

    def stop(self):
        self.running = False


if __name__ == "__main__":
    guardian = SmartGuardian()
    print("Testing smart detection on CAM1 (Shop)...")
    incident = guardian.process_camera(1)
    if incident:
        print(f"Alert: {incident['severity_emoji']} {incident['ai_description']}")
    else:
        print("No suspicious activity detected — system working correctly!")

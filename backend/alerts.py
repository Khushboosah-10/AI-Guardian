"""
AI Guardian - Alert System
Sends WhatsApp alerts to all family members
"""

import os
import json
from datetime import datetime
from twilio.rest import Client
from groq import Groq
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

load_dotenv('/Users/admin/Downloads/ai_guardian/.env')

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
GROQ_KEY = os.getenv("GROQ_API_KEY")

# All family members
TWILIO_TO_LIST = [t for t in [
    os.getenv("TWILIO_WHATSAPP_TO_1"),
    os.getenv("TWILIO_WHATSAPP_TO_2"),
    os.getenv("TWILIO_WHATSAPP_TO_3"),
    os.getenv("TWILIO_WHATSAPP_TO_4"),
    os.getenv("TWILIO_WHATSAPP_TO_5"),
] if t]

# Cloudinary config
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


def upload_to_cloudinary(file_path, resource_type="image"):
    try:
        result = cloudinary.uploader.upload(
            file_path,
            folder="ai_guardian",
            resource_type=resource_type,
        )
        print(f"✅ Uploaded: {result['secure_url']}")
        return result["secure_url"]
    except Exception as e:
        print(f"❌ Cloudinary error: {e}")
        return None


def generate_ai_description(incident):
    if not GROQ_KEY:
        return f"{incident['severity_emoji']} {incident['severity_label']} on {incident['cam_name']}"
    try:
        client = Groq(api_key=GROQ_KEY)
        detections = [d['class'] for d in incident['detections']]
        events = [e['message'] for e in incident.get('events', [])]
        prompt = f"""You are AI Guardian security system.
Generate a brief 1-2 sentence alert for:
- Camera: {incident['cam_name']}
- Detected: {', '.join(detections)}
- Events: {', '.join(events) if events else 'Activity detected'}
- Time: {datetime.fromisoformat(incident['timestamp']).strftime('%I:%M %p')}
- Severity: {incident['severity_label']}
Be concise and professional. Max 30 words."""
        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq error: {e}")
        return f"{incident['severity_emoji']} {incident['severity_label']} detected"


def format_whatsapp_message(incident, ai_description):
    timestamp = datetime.fromisoformat(incident['timestamp'])
    time_str = timestamp.strftime("%I:%M %p")
    date_str = timestamp.strftime("%d %b %Y")
    detections = [f"{d['class']} ({d['confidence']:.0%})" for d in incident['detections']]
    message = f"""🚨 *AI Guardian Alert*

📍 *Camera:* {incident['cam_name']}
🕐 *Time:* {time_str}, {date_str}
{incident['severity_emoji']} *Event:* {incident['severity_label']}
🎯 *Detected:* {', '.join(detections)}

💬 _{ai_description}_

🆔 {incident['id']}"""
    return message


def send_whatsapp_alert(incident, image_path):
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_TO_LIST:
        print("⚠️  Twilio not configured")
        print(f"Would alert: {incident['severity_emoji']} {incident['severity_label']}")
        return False

    try:
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        ai_desc = generate_ai_description(incident)
        message_body = format_whatsapp_message(incident, ai_desc)

        # Upload image once
        image_url = None
        if image_path and os.path.exists(image_path):
            image_url = upload_to_cloudinary(image_path, "image")

        # Upload video once
        video_url = None
        if incident.get("video"):
            try:
                from smart_detector import VIDEOS_DIR
                video_path = os.path.join(VIDEOS_DIR, incident["video"])
                if os.path.exists(video_path):
                    video_url = upload_to_cloudinary(video_path, "video")
            except Exception:
                pass

        # Send to ALL family members
        for recipient in TWILIO_TO_LIST:
            try:
                # Text alert
                client.messages.create(
                    from_=TWILIO_FROM,
                    to=recipient,
                    body=message_body,
                )
                # Image
                if image_url:
                    client.messages.create(
                        from_=TWILIO_FROM,
                        to=recipient,
                        body=f"📸 Evidence — {incident['cam_name']}",
                        media_url=[image_url],
                    )
                # Video
                if video_url:
                    client.messages.create(
                        from_=TWILIO_FROM,
                        to=recipient,
                        body=f"🎥 Video clip — {incident['cam_name']}",
                        media_url=[video_url],
                    )
                print(f"✅ Alert sent to {recipient}")
            except Exception as e:
                print(f"❌ Failed {recipient}: {e}")

        return True

    except Exception as e:
        print(f"❌ Alert error: {e}")
        return False


def send_daily_report(incidents):
    if not incidents:
        return

    today = datetime.now().strftime("%d %b %Y")
    total = len(incidents)
    by_severity = {}
    by_camera = {}

    for inc in incidents:
        sev = inc.get("severity_label", "Unknown")
        cam = inc.get("cam_name", "Unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_camera[cam] = by_camera.get(cam, 0) + 1

    severity_lines = "\n".join([f"  • {k}: {v}" for k, v in by_severity.items()])
    camera_lines = "\n".join([f"  • {k}: {v}" for k, v in by_camera.items()])

    message = f"""📊 *AI Guardian Daily Report*
📅 {today}

Total Incidents: *{total}*

By Event Type:
{severity_lines}

By Camera:
{camera_lines}

Stay safe! 🛡️"""

    if TWILIO_SID and TWILIO_TOKEN and TWILIO_TO_LIST:
        try:
            client = Client(TWILIO_SID, TWILIO_TOKEN)
            for recipient in TWILIO_TO_LIST:
                client.messages.create(
                    from_=TWILIO_FROM,
                    to=recipient,
                    body=message,
                )
            print(f"✅ Daily report sent to {len(TWILIO_TO_LIST)} recipients!")
        except Exception as e:
            print(f"❌ Daily report error: {e}")


if __name__ == "__main__":
    print(f"Configured recipients: {len(TWILIO_TO_LIST)}")
    for r in TWILIO_TO_LIST:
        print(f"  - {r}")

    from datetime import datetime
    test_incident = {
        "id": "INC_TEST_FAMILY",
        "timestamp": datetime.now().isoformat(),
        "cam_id": 2,
        "cam_name": "Street Left (Entrance Gate)",
        "detections": [{"class": "person", "confidence": 0.85, "event_type": "person"}],
        "events": [{"type": "loitering", "message": "Person loitering for 35 seconds near gate"}],
        "severity": "loitering",
        "severity_label": "Suspicious Loitering",
        "severity_emoji": "🟠",
        "ai_description": "A person is standing suspiciously near the entrance gate for over 30 seconds.",
        "image": None,
        "video": None,
    }
    print("\nSending test alert to all family members...")
    send_whatsapp_alert(test_incident, None)

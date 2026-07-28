"""
AI Guardian - Telegram Alert System
Sends alerts to family group with images and videos
"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/Users/admin/Downloads/ai_guardian/.env')

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text):
    """Send text message to group"""
    try:
        r = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Telegram message error: {e}")
        return False


def send_photo(image_path, caption=""):
    """Send photo to group"""
    try:
        with open(image_path, "rb") as f:
            r = requests.post(f"{API_URL}/sendPhoto", 
                data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
                files={"photo": f},
                timeout=30,
            )
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Telegram photo error: {e}")
        return False


def send_video(video_path, caption=""):
    """Send video to group"""
    try:
        with open(video_path, "rb") as f:
            r = requests.post(f"{API_URL}/sendVideo",
                data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
                files={"video": f},
                timeout=60,
            )
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Telegram video error: {e}")
        return False


def format_message(incident, ai_description):
    """Format alert message"""
    timestamp = datetime.fromisoformat(incident['timestamp'])
    time_str = timestamp.strftime("%I:%M %p")
    date_str = timestamp.strftime("%d %b %Y")
    detections = [f"{d['class']} ({d['confidence']:.0%})" for d in incident['detections']]

    return f"""🚨 *AI Guardian Alert*

📍 *Camera:* {incident['cam_name']}
🕐 *Time:* {time_str}, {date_str}
{incident['severity_emoji']} *Event:* {incident['severity_label']}
🎯 *Detected:* {', '.join(detections)}

💬 _{ai_description}_

🆔 `{incident['id']}`"""


def send_telegram_alert(incident, image_path):
    """Send full alert — text + image + video"""
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️  Telegram not configured")
        return False

    try:
        # Generate AI description
        ai_desc = incident.get("ai_description", f"{incident['severity_label']} detected")
        message = format_message(incident, ai_desc)

        # Send image with caption (combines text + photo in one message)
        if image_path and os.path.exists(image_path):
            success = send_photo(image_path, caption=message)
            if success:
                print(f"✅ Telegram alert sent with image!")
            else:
                # Fallback — send text only
                send_message(message)
                print(f"✅ Telegram text alert sent!")
        else:
            send_message(message)
            print(f"✅ Telegram text alert sent!")

        # Send video if available
        if incident.get("video"):
            try:
                from smart_detector import VIDEOS_DIR
                video_path = os.path.join(VIDEOS_DIR, incident["video"])
                if os.path.exists(video_path):
                    send_video(video_path, caption=f"🎥 Video clip — {incident['cam_name']}")
                    print(f"✅ Telegram video sent!")
            except Exception as e:
                print(f"Video send error: {e}")

        return True

    except Exception as e:
        print(f"❌ Telegram alert error: {e}")
        return False


def send_daily_report(incidents):
    """Send daily security summary"""
    if not incidents:
        send_message("✅ *AI Guardian Daily Report*\n\nNo incidents today. All clear! 🛡️")
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

    send_message(message)
    print("✅ Daily report sent!")


if __name__ == "__main__":
    print("Testing Telegram connection...")
    
    # Test message
    result = send_message("🤖 *AI Guardian* connected successfully!\n\nYour home security system is online. You will receive alerts here when suspicious activity is detected.")
    
    if result:
        print("✅ Telegram working!")
    else:
        print("❌ Telegram failed — check BOT_TOKEN and CHAT_ID in .env")

import os
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = "primary"

SOURCE_TAG = "https://alnafi.com/live-schedule"

def get_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

def is_alnafi_event(ev: dict) -> bool:
    desc = (ev.get("description") or "").lower()

    ext = (ev.get("extendedProperties") or {}).get("private") or {}
    if "alnafi_key" in ext:
        return True

    if SOURCE_TAG.lower() in desc:
        return True

    if "key:" in desc and "alnafi" in desc:
        return True

    return False

def delete_matching_events():
    service = get_service()

    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=730)).isoformat()
    time_max = (now + timedelta(days=730)).isoformat()

    print(f"Searching events in range:\n  timeMin={time_min}\n  timeMax={time_max}\nCalendar: {CALENDAR_ID}\n")

    page_token = None
    deleted = 0
    scanned = 0

    while True:
        resp = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=2500,
            pageToken=page_token
        ).execute()

        items = resp.get("items", [])
        scanned += len(items)

        for ev in items:
            if not is_alnafi_event(ev):
                continue

            summary = ev.get("summary", "(no title)")
            start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
            print(f"Deleting: {summary} | {start}")
            service.events().delete(calendarId=CALENDAR_ID, eventId=ev["id"]).execute()
            deleted += 1

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    print(f"\nDone.")

if __name__ == "__main__":
    delete_matching_events()

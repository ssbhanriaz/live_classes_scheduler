import os
import re
import hashlib
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from dateutil import tz

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

LIVE_SCHEDULE_URL = "https://alnafi.com/live-schedule"
CALENDAR_ID = "primary"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

TIMEZONE = "Asia/Karachi"
DEFAULT_DURATION_MIN = 60

ORDINAL_RE = re.compile(r"(\d+)(st|nd|rd|th)", re.IGNORECASE)
TRACK_RE = re.compile(r"\((.*?)\)\s*$") 


def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def clean_ordinal_date(s: str) -> str:
    return ORDINAL_RE.sub(r"\1", s.strip())


def parse_dates(date_text: str) -> list[datetime]:
    parts = [p.strip() for p in date_text.split("/") if p.strip()]
    out = []
    for p in parts:
        out.append(datetime.strptime(clean_ordinal_date(p), "%d %b %Y"))
    return out


def extract_pkt_time(time_text: str) -> str | None:
    left = time_text.split("/")[0].strip()
    m = re.search(r"(\d{1,2}:\d{2}\s*[AP]M)", left, re.IGNORECASE)
    return m.group(1).upper() if m else None


def extract_track(class_name: str) -> str:
    m = TRACK_RE.search(class_name.strip())
    return m.group(1).strip() if m else "Unknown"


def strip_track_from_title(class_name: str) -> str:
    return TRACK_RE.sub("", class_name).strip()


def make_key(summary: str, start_iso: str) -> str:
    raw = f"{summary}|{start_iso}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def calendar_has_key(service, key: str, day_start: datetime, day_end: datetime) -> bool:
    resp = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        singleEvents=True,
        privateExtendedProperty=f"alnafi_key={key}",
        maxResults=1,
    ).execute()
    return len(resp.get("items", [])) > 0


def create_event(service, summary: str, description: str, start_dt: datetime, end_dt: datetime):
    key = make_key(summary, start_dt.isoformat())
    day_start = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    if calendar_has_key(service, key, day_start, day_end):
        return

    event = {
        "summary": summary,
        "description": f"{description}\nSource: {LIVE_SCHEDULE_URL}\nKey: {key}",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TIMEZONE},
        "extendedProperties": {"private": {"alnafi_key": key}},
        "reminders": {"useDefault": True},
    }
    service.events().insert(calendarId=CALENDAR_ID, body=event).execute()


def pick_best_table(soup: BeautifulSoup):
    tables = soup.find_all("table")
    if not tables:
        return None

    best = None
    best_score = -1
    for t in tables:
        text = t.get_text(" ", strip=True).lower()
        score = 0
        if "class name" in text and "instructor" in text and "date" in text and "time" in text:
            score += 100
        score += len(t.find_all("tr"))
        if score > best_score:
            best = t
            best_score = score
    return best


def scrape_schedule():
    html = requests.get(LIVE_SCHEDULE_URL, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    table = pick_best_table(soup)
    if not table:
        raise RuntimeError("Could not find schedule table.")

    results = []
    seen_rows = set() 

    rows = table.find_all("tr")
    for tr in rows[1:]:
        tds = tr.find_all(["td", "th"])
        if len(tds) < 5:
            continue

        class_name_full = tds[1].get_text(" ", strip=True)
        instructor = tds[2].get_text(" ", strip=True)
        date_text = tds[3].get_text(" ", strip=True)
        time_text = tds[4].get_text(" ", strip=True)

        title = strip_track_from_title(class_name_full)
        track = extract_track(class_name_full)

        if "IELTS" in title.upper():
            continue

        if "TBD" in date_text.upper() or "TBD" in time_text.upper():
            continue

        if "MONDAY TO FRIDAY" in date_text.upper():
            continue

        row_key = (title, instructor, track, date_text, time_text)
        if row_key in seen_rows:
            continue
        seen_rows.add(row_key)

        pkt_time = extract_pkt_time(time_text)
        if not pkt_time:
            continue

        try:
            dates = parse_dates(date_text)
        except Exception:
            continue

        results.append({
            "title": title,
            "track": track,
            "instructor": instructor,
            "dates": dates,
            "pkt_time": pkt_time,
        })

    return results


def prompt_program_choice() -> int:
    print("Choose your program to import:")
    print("  1) Diploma in Cloud Cyber Security (only Cloud Cyber Security)")
    print("  2) Diploma in DevOps and Cloud Advancement (DevOps + Cloud Cyber Security)")
    print("  3) Diploma in SysOps & Cloud Advancement (SysOps + Cloud Cyber Security)")
    print("  4) AiOps (All tracks)")
    while True:
        x = input("Enter 1-4: ").strip()
        if x in {"1", "2", "3", "4"}:
            return int(x)
        print("Please enter 1, 2, 3, or 4.")


def choose_tracks_by_program(all_tracks: set[str], choice: int) -> set[str]:
    def contains_kw(t: str, kw: str) -> bool:
        return kw.lower() in t.lower()

    ccs = {t for t in all_tracks if contains_kw(t, "cloud cyber security")}
    devops = {t for t in all_tracks if contains_kw(t, "devops")}
    sysops = {t for t in all_tracks if contains_kw(t, "sysops")}

    if choice == 1:
        return set(ccs)
    if choice == 2:
        return set(devops) | set(ccs)
    if choice == 3:
        return set(sysops) | set(ccs)
    return set(all_tracks)  


def main():
    service = get_calendar_service()
    local_tz = tz.gettz(TIMEZONE)

    items = scrape_schedule()

    all_tracks = sorted({x["track"] for x in items})
    allowed_tracks = choose_tracks_by_program(set(all_tracks), prompt_program_choice())

    print("\nTracks detected on page:")
    for t in all_tracks:
        print(" - " + t)

    print("\nTracks that will be imported based on your selection:")
    for t in sorted(allowed_tracks):
        print(" - " + t)

        seen_in_run = set()

    created = 0
    skipped = 0

    for it in items:
        if it["track"] not in allowed_tracks:
            continue

        t = datetime.strptime(it["pkt_time"], "%I:%M %p")

        for d in it["dates"]:
            start_dt = datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=local_tz)
            end_dt = start_dt + timedelta(minutes=DEFAULT_DURATION_MIN)

            in_run_key = (it["title"], start_dt.isoformat())
            if in_run_key in seen_in_run:
                skipped += 1
                continue
            seen_in_run.add(in_run_key)

            before = created
            create_event(
                service=service,
                summary=it["title"],
                description=f"Instructor: {it['instructor']}\nTrack: {it['track']}",
                start_dt=start_dt,
                end_dt=end_dt,
            )
            created += 1 if created == before else 0

    print("\nImport finished.")


if __name__ == "__main__":
    main()
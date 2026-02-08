AlNafi Live Schedule to Google Calendar Importer

A Python automation tool that scrapes AlNafi’s live class schedule
and imports selected diploma classes into Google Calendar.

---

## Features

- Program-based import:
  - Diploma in Cloud Cyber Security
  - Diploma in DevOps and Cloud Advancement
  - Diploma in SysOps & Cloud Advancement
  - AiOps (all tracks)
- Google Calendar API integration using OAuth2
- Safe credential handling (no secrets committed)
- Optional cleanup script to remove imported events

---

## Tech Stack

- Python 3.9+
- BeautifulSoup (HTML parsing)
- Requests (HTTP)
- Google Calendar API
- OAuth2 (Desktop application flow)

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/ssbhanriaz/live_classes_scheduler.git

cd live_classes_scheduler
```

### 2. Install dependencies
Make sure Python 3.9 or higher is installed.

```bash
pip install -r requirements.txt
```

### 3. Create Google OAuth credentials (required)

Each user must create their own OAuth credentials.

Go to Google Cloud Console

Create a new project

Enable Google Calendar API

Create OAuth Client ID

Application type: Desktop app

Download the credentials file

Rename it to:

credentials.json
Place it in the project directory

### 4. Run the importer

```bash
python live_schedule_to_calendar.py
```
On first run:

A browser window will open

Sign in to your Google account

Approve calendar access

A token.json file will be created automatically.

---

## Removing Imported Events 
To delete all events created by this tool:

```bash
python delete_events.py
```
This script safely removes only events created by the importer.

---

## Security Notes
credentials.json and token.json are not included in this repository

Each user must generate their own OAuth credentials

"""
Calendar & Agenda Manager for JASVA with Multi-Calendar Google Sync.
Supports:
1. Unlimited Simultaneous Calendar Feeds (Primary, Birthdays, Holidays, Exams, Work)
2. Direct Google Calendar OAuth 2.0 (2-way live sync)
3. Google Calendar Secret iCal / ICS Feeds
4. Local offline caching and recurring event rule expansion (RRULE)
5. Memory Scheduler integration for desktop reminders
"""

import os
import json
import time
import uuid
import threading
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Optional, Any

from backend.sys_utils import DB_DIR, logger
from backend.memory_scheduler import add_schedule, get_active_schedules

CALENDAR_FILE = os.path.join(DB_DIR, "calendar_events.json")
GOOGLE_TOKEN_FILE = os.path.join(DB_DIR, "google_token.json")
GOOGLE_CREDS_FILE = os.path.join(DB_DIR, "google_credentials.json")
GOOGLE_ICAL_FILE = os.path.join(DB_DIR, "google_ical_url.txt")
FEEDS_FILE = os.path.join(DB_DIR, "calendar_feeds.json")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly"
]

DEFAULT_COLORS = ["#00f2fe", "#ff3b30", "#00ff87", "#c026d3", "#ff8800", "#4facfe"]


def _ensure_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)
    if not os.path.exists(CALENDAR_FILE):
        with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)


def load_calendar_events() -> List[Dict[str, Any]]:
    """Load all calendar events from disk cache."""
    _ensure_db()
    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.error(f"Error loading calendar events: {e}")
    return []


def save_calendar_events(events: List[Dict[str, Any]]) -> bool:
    """Save all calendar events to disk cache."""
    _ensure_db()
    try:
        with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving calendar events: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# MULTI-CALENDAR FEED MANAGEMENT
# ══════════════════════════════════════════════════════════════════

def get_calendar_feeds() -> List[Dict[str, Any]]:
    """Retrieve all linked calendar feeds."""
    _ensure_db()
    feeds = []
    if os.path.exists(FEEDS_FILE):
        try:
            with open(FEEDS_FILE, "r", encoding="utf-8") as f:
                feeds = json.load(f)
        except Exception:
            feeds = []

    # Auto-migrate legacy single iCal URL file if feeds is empty
    if not feeds and os.path.exists(GOOGLE_ICAL_FILE):
        try:
            with open(GOOGLE_ICAL_FILE, "r", encoding="utf-8") as f:
                url = f.read().strip()
                if url:
                    feeds = [{
                        "id": "feed_primary",
                        "name": "Primary Calendar",
                        "url": url,
                        "color": "#00f2fe",
                        "active": True
                    }]
                    save_calendar_feeds(feeds)
        except Exception:
            pass

    return feeds


def save_calendar_feeds(feeds: List[Dict[str, Any]]) -> bool:
    """Save calendar feeds configuration to disk."""
    _ensure_db()
    try:
        with open(FEEDS_FILE, "w", encoding="utf-8") as f:
            json.dump(feeds, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving calendar feeds: {e}")
        return False


def add_calendar_feed(name: str, url: str, color: Optional[str] = None) -> Dict[str, Any]:
    """Add a new calendar feed (e.g. Birthdays, Work, Holidays) and trigger sync."""
    clean_url = url.strip()
    if not clean_url.startswith("http"):
        return {"status": "error", "message": "Invalid iCal URL. Must start with https://"}

    feeds = get_calendar_feeds()
    # Check if URL already exists
    for f in feeds:
        if f.get("url") == clean_url:
            f["name"] = name.strip() or f.get("name", "Calendar")
            if color:
                f["color"] = color
            save_calendar_feeds(feeds)
            sync_from_google()
            return {"status": "success", "message": "Calendar updated", "feeds": feeds}

    feed_id = f"feed_{uuid.uuid4().hex[:8]}"
    color_choice = color or DEFAULT_COLORS[len(feeds) % len(DEFAULT_COLORS)]
    new_feed = {
        "id": feed_id,
        "name": name.strip() or f"Calendar {len(feeds) + 1}",
        "url": clean_url,
        "color": color_choice,
        "active": True
    }
    feeds.append(new_feed)
    save_calendar_feeds(feeds)

    # Trigger immediate sync
    sync_res = sync_from_google()
    return {
        "status": "success",
        "message": f"Added '{new_feed['name']}' ({sync_res.get('count', 0)} total events synced)",
        "feeds": feeds,
        "feed": new_feed
    }


def remove_calendar_feed(feed_id: str) -> Dict[str, Any]:
    """Remove a linked calendar feed and prune its events."""
    feeds = get_calendar_feeds()
    new_feeds = [f for f in feeds if f.get("id") != feed_id]
    save_calendar_feeds(new_feeds)

    # Prune events belonging to this feed
    events = load_calendar_events()
    remaining_events = [e for e in events if e.get("feed_id") != feed_id]
    save_calendar_events(remaining_events)

    # Re-sync remaining feeds
    sync_from_google()
    return {"status": "success", "feeds": new_feeds}


# ══════════════════════════════════════════════════════════════════
# GOOGLE CALENDAR API OAUTH 2.0 INTEGRATION
# ══════════════════════════════════════════════════════════════════

def get_google_oauth_creds():
    """Get or refresh Google OAuth2 credentials."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = None
        if os.path.exists(GOOGLE_TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
            except Exception as e:
                logger.debug(f"Error reading google token file: {e}")

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                logger.debug(f"Error refreshing google token: {e}")
                creds = None

        return creds
    except Exception as e:
        logger.debug(f"Google OAuth check failed: {e}")
        return None


def get_google_service():
    """Build and return an authorized Google Calendar Resource."""
    creds = get_google_oauth_creds()
    if not creds or not creds.valid:
        return None
    try:
        from googleapiclient.discovery import build
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        logger.error(f"Failed to build Google Calendar service: {e}")
        return None


def start_google_oauth_flow(credentials_json_content: Optional[str] = None) -> Dict[str, Any]:
    """Start interactive Google OAuth login flow."""
    _ensure_db()
    if credentials_json_content:
        try:
            with open(GOOGLE_CREDS_FILE, "w", encoding="utf-8") as f:
                f.write(credentials_json_content)
        except Exception as e:
            return {"status": "error", "message": f"Could not save credentials: {e}"}

    search_paths = [
        GOOGLE_CREDS_FILE,
        os.path.join(os.getcwd(), "credentials.json"),
        os.path.join(os.path.dirname(__file__), "credentials.json"),
        os.path.join(os.getcwd(), "client_secret.json")
    ]
    target_creds_path = next((p for p in search_paths if os.path.exists(p)), None)

    if not target_creds_path:
        return {
            "status": "error",
            "message": "credentials.json not found. Paste your Google Cloud OAuth Client JSON or add iCal links."
        }

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(target_creds_path, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True, timeout_seconds=120)
        with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

        sync_from_google()
        return {"status": "success", "message": "Google Calendar OAuth linked successfully!"}
    except Exception as e:
        logger.error(f"Google OAuth login error: {e}")
        return {"status": "error", "message": str(e)}


# ══════════════════════════════════════════════════════════════════
# MULTI-FEED SYNC ENGINE
# ══════════════════════════════════════════════════════════════════

def _parse_ical_stream(ical_bytes: bytes, feed_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse raw iCal bytes into structured event dicts."""
    from icalendar import Calendar
    from dateutil.rrule import rrulestr

    cal = Calendar.from_ical(ical_bytes)
    events = []
    local_tz = datetime.now().astimezone().tzinfo
    feed_id = feed_info.get("id", "feed_default")
    feed_name = feed_info.get("name", "Google Calendar")
    feed_color = feed_info.get("color", "#00f2fe")

    for component in cal.walk():
        if component.name == "VEVENT":
            try:
                summary = str(component.get("summary") or "Google Event")
                dtstart_prop = component.get("dtstart")
                dtend_prop = component.get("dtend")
                description = str(component.get("description") or "")
                uid = str(component.get("uid") or uuid.uuid4())
                rrule = component.get("rrule")

                if not dtstart_prop or not hasattr(dtstart_prop, "dt"):
                    continue

                dtstart = dtstart_prop.dt
                cat = "WORK"
                s_lower = summary.lower()
                if any(k in s_lower for k in ["birthday", "bday", "\U0001f382"]):
                    cat = "BIRTHDAY"
                elif any(k in s_lower for k in ["exam", "test", "quiz", "midterm", "final", "external"]):
                    cat = "ALERT"
                elif any(k in s_lower for k in ["meet", "sync", "call", "zoom", "huddle", "interview"]):
                    cat = "MEET"
                elif any(k in s_lower for k in ["gym", "doctor", "health", "med", "run", "workout"]):
                    cat = "HEALTH"
                elif any(k in s_lower for k in ["urgent", "deadline", "pay", "bill"]):
                    cat = "URGENT"
                elif any(k in s_lower for k in ["holiday", "party", "dinner", "lunch", "movie", "trip"]):
                    cat = "PERSONAL"

                # Expand Recurring Rules (RRULE) between 2024 and 2028
                if rrule:
                    try:
                        dt_for_rule = dtstart if isinstance(dtstart, datetime) else datetime(dtstart.year, dtstart.month, dtstart.day)
                        rule_str = rrule.to_ical().decode("utf-8")
                        rule = rrulestr(rule_str, dtstart=dt_for_rule)
                        start_win = datetime(2024, 1, 1, tzinfo=dt_for_rule.tzinfo if isinstance(dt_for_rule, datetime) else None)
                        end_win = datetime(2028, 12, 31, tzinfo=dt_for_rule.tzinfo if isinstance(dt_for_rule, datetime) else None)
                        occurrences = rule.between(start_win, end_win, inc=True)
                        for occ in occurrences:
                            occ_local = occ.astimezone(local_tz) if occ.tzinfo else occ
                            events.append({
                                "id": f"{feed_id}_{uid[:10]}_{occ_local.strftime('%Y%m%d')}",
                                "title": summary,
                                "date": occ_local.strftime("%Y-%m-%d"),
                                "time": occ_local.strftime("%H:%M"),
                                "category": cat,
                                "description": description,
                                "duration_mins": 60,
                                "completed": False,
                                "source": "google_ical",
                                "feed_id": feed_id,
                                "feed_name": feed_name,
                                "feed_color": feed_color,
                                "updated_at": time.time()
                            })
                        continue
                    except Exception as e:
                        logger.debug(f"Could not parse RRULE for event '{summary}': {e}")

                # Single Event
                if isinstance(dtstart, datetime):
                    dt_local = dtstart.astimezone(local_tz) if dtstart.tzinfo else dtstart
                    event_date = dt_local.strftime("%Y-%m-%d")
                    event_time = dt_local.strftime("%H:%M")
                    duration_mins = 60
                    if dtend_prop and hasattr(dtend_prop, "dt") and isinstance(dtend_prop.dt, datetime):
                        duration_mins = max(15, int((dtend_prop.dt - dtstart).total_seconds() / 60))
                elif isinstance(dtstart, date):
                    event_date = dtstart.strftime("%Y-%m-%d")
                    event_time = "09:00"
                    duration_mins = 1440
                else:
                    continue

                events.append({
                    "id": f"{feed_id}_{uid[:14]}",
                    "title": summary,
                    "date": event_date,
                    "time": event_time,
                    "category": cat,
                    "description": description,
                    "duration_mins": duration_mins,
                    "completed": False,
                    "source": "google_ical",
                    "feed_id": feed_id,
                    "feed_name": feed_name,
                    "feed_color": feed_color,
                    "updated_at": time.time()
                })
            except Exception as e:
                logger.debug(f"Error parsing VEVENT: {e}")
                continue

    return events


def sync_from_google() -> Dict[str, Any]:
    """
    Sync all registered Google Calendar feeds (and OAuth primary calendar if available).
    Merges all events into calendar_events.json.
    """
    import urllib.request

    all_fetched = []
    feeds = get_calendar_feeds()
    synced_feed_names = []

    # 1. Sync iCal Feeds
    for feed in feeds:
        if not feed.get("active", True) or not feed.get("url"):
            continue
        url = feed["url"]
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JASVA/2.0"}
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                ical_bytes = response.read()
            evs = _parse_ical_stream(ical_bytes, feed)
            all_fetched.extend(evs)
            synced_feed_names.append(f"{feed['name']} ({len(evs)})")
        except Exception as e:
            logger.error(f"Error syncing feed '{feed.get('name')}': {e}")

    # 2. Sync OAuth API: Fetch ALL calendars in user's Gmail account (Primary, Birthdays, Holidays, etc.)
    service = get_google_service()
    if service:
        try:
            now_iso = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
            future_iso = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

            # Query all calendars in user's Google account
            cal_list = service.calendarList().list().execute()
            items = cal_list.get("items", [])
            for c_item in items:
                c_id = c_item.get("id")
                c_name = c_item.get("summary", "Google Calendar")
                c_color = c_item.get("backgroundColor", "#4285f4")
                try:
                    events_result = service.events().list(
                        calendarId=c_id,
                        timeMin=now_iso,
                        timeMax=future_iso,
                        maxResults=250,
                        singleEvents=True,
                        orderBy="startTime"
                    ).execute()

                    for item in events_result.get("items", []):
                        summary = item.get("summary", "Event")
                        start = item.get("start", {})
                        start_str = start.get("dateTime") or start.get("date")
                        if not start_str:
                            continue
                        if "T" in start_str:
                            dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                            local_dt = dt.astimezone()
                            event_date = local_dt.strftime("%Y-%m-%d")
                            event_time = local_dt.strftime("%H:%M")
                        else:
                            event_date = start_str
                            event_time = "09:00"

                        cat = "BIRTHDAY" if "birthday" in c_name.lower() or "birthday" in summary.lower() else ("ALERT" if "exam" in summary.lower() else "WORK")
                        all_fetched.append({
                            "id": f"gapi_{item.get('id', uuid.uuid4())}",
                            "google_id": item.get("id"),
                            "title": summary,
                            "date": event_date,
                            "time": event_time,
                            "category": cat,
                            "description": item.get("description", ""),
                            "duration_mins": 60,
                            "completed": False,
                            "source": "google_api",
                            "feed_name": c_name,
                            "feed_color": c_color,
                            "html_link": item.get("htmlLink", "")
                        })
                    synced_feed_names.append(f"{c_name}")
                except Exception as ex:
                    logger.debug(f"Error reading calendar '{c_name}': {ex}")
        except Exception as e:
            logger.error(f"OAuth sync error: {e}")

    # Deduplicate events by (title, date, time) to handle overlapping calendars gracefully
    seen = set()
    deduped = []
    for ev in all_fetched:
        key = (ev.get("title"), ev.get("date"), ev.get("time"))
        if key not in seen:
            seen.add(key)
            deduped.append(ev)

    # Retain manual local events created within JASVA
    local_events = [e for e in load_calendar_events() if e.get("source") not in ("google_ical", "google_api")]
    combined = local_events + deduped
    save_calendar_events(combined)

    logger.info(f"Multi-Calendar Sync complete: {len(deduped)} events across {len(feeds)} calendars.")
    return {
        "status": "success",
        "count": len(deduped),
        "feeds_synced": synced_feed_names,
        "message": f"Synced {len(deduped)} events across {len(feeds)} calendars"
    }


def get_google_calendar_status() -> Dict[str, Any]:
    """Get multi-calendar connection status and list of feeds."""
    feeds = get_calendar_feeds()
    creds = get_google_oauth_creds()
    has_oauth = bool(creds and creds.valid)
    events = load_calendar_events()

    return {
        "connected": len(feeds) > 0 or has_oauth,
        "mode": "multi_feed" if len(feeds) > 1 else ("ical" if feeds else ("oauth" if has_oauth else "local")),
        "feed_count": len(feeds),
        "feeds": feeds,
        "has_oauth": has_oauth,
        "event_count": len(events)
    }


# ══════════════════════════════════════════════════════════════════
# EVENT CRUD OPERATIONS
# ══════════════════════════════════════════════════════════════════

def add_event(
    title: str,
    event_date: str,
    event_time: str = "09:00",
    category: str = "WORK",
    description: str = "",
    duration_mins: int = 60,
    set_reminder: bool = True
) -> Dict[str, Any]:
    """Add a new calendar event."""
    events = load_calendar_events()
    event_id = str(uuid.uuid4())[:8]

    if not event_date:
        event_date = date.today().isoformat()
    if not event_time:
        event_time = "09:00"

    event = {
        "id": event_id,
        "title": title.strip() or "Untitled Event",
        "date": event_date,
        "time": event_time,
        "category": category.upper(),
        "description": description.strip(),
        "duration_mins": duration_mins,
        "completed": False,
        "source": "local",
        "feed_name": "Local",
        "feed_color": "#00f2fe",
        "created_at": time.time()
    }

    events.append(event)
    save_calendar_events(events)

    if set_reminder:
        try:
            dt_str = f"{event_date} {event_time}"
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            trigger_epoch = dt_obj.timestamp()
            if trigger_epoch > time.time():
                add_schedule(
                    schedule_type="reminder",
                    label=f"Calendar: {event['title']}",
                    trigger_time=trigger_epoch
                )
        except Exception:
            pass

    return event


def delete_event(event_id: str) -> bool:
    """Delete event by ID."""
    events = load_calendar_events()
    new_events = [e for e in events if e.get("id") != event_id and e.get("google_id") != event_id]
    if len(new_events) < len(events):
        return save_calendar_events(new_events)
    return False


def toggle_event_status(event_id: str) -> Optional[Dict[str, Any]]:
    """Toggle completed status of an event."""
    events = load_calendar_events()
    for e in events:
        if e.get("id") == event_id:
            e["completed"] = not e.get("completed", False)
            save_calendar_events(events)
            return e
    return None


def get_events_for_month(year: int, month: int) -> List[Dict[str, Any]]:
    """Get all events for a given year and month."""
    events = load_calendar_events()
    prefix = f"{year:04d}-{month:02d}"
    return [e for e in events if e.get("date", "").startswith(prefix)]


def get_events_for_date(target_date: str) -> List[Dict[str, Any]]:
    """Get all events for a specific date."""
    events = load_calendar_events()
    day_events = [e for e in events if e.get("date") == target_date]
    day_events.sort(key=lambda x: x.get("time", "00:00"))
    return day_events


def get_upcoming_agenda(limit: int = 20) -> List[Dict[str, Any]]:
    """Get upcoming events starting from today."""
    today_str = date.today().isoformat()
    events = load_calendar_events()
    upcoming = [e for e in events if e.get("date", "") >= today_str and not e.get("completed", False)]
    upcoming.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))

    try:
        schedules = get_active_schedules()
        for s in schedules:
            trigger_time = s.get("trigger_time", 0)
            if trigger_time:
                dt = datetime.fromtimestamp(trigger_time)
                s_date = dt.strftime("%Y-%m-%d")
                s_time = dt.strftime("%H:%M")
                if s_date >= today_str:
                    upcoming.append({
                        "id": s.get("id", f"sched_{int(trigger_time)}"),
                        "title": s.get("label") or s.get("task") or "Scheduled Reminder",
                        "date": s_date,
                        "time": s_time,
                        "category": "ALERT",
                        "description": "System scheduled alarm / reminder",
                        "completed": False,
                        "is_schedule": True
                    })
        upcoming.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
    except Exception:
        pass

    return upcoming[:limit]


def export_to_ics() -> str:
    """Generate and save standard iCalendar (.ics) file."""
    events = load_calendar_events()
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//JASVA//Quantum OS Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:JASVA Unified Calendar"
    ]

    for ev in events:
        try:
            ev_date = ev.get("date", "")
            ev_time = ev.get("time", "09:00")
            dt_str = f"{ev_date} {ev_time}"
            dt_start = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            dur = ev.get("duration_mins", 60)
            dt_end = dt_start + timedelta(minutes=dur)

            t_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            t_start = dt_start.strftime("%Y%m%dT%H%M%S")
            t_end = dt_end.strftime("%Y%m%dT%H%M%S")

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{ev.get('id')}@jasva.quantum",
                f"DTSTAMP:{t_stamp}",
                f"DTSTART:{t_start}",
                f"DTEND:{t_end}",
                f"SUMMARY:{ev.get('title', 'Event')}",
                f"DESCRIPTION:{ev.get('description', '')}",
                f"CATEGORIES:{ev.get('category', 'WORK')}",
                "END:VEVENT"
            ])
        except Exception:
            continue

    lines.append("END:VCALENDAR")
    ics_path = os.path.join(DB_DIR, "jasva_calendar.ics")
    with open(ics_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines) + "\r\n")

    return ics_path


# ══════════════════════════════════════════════════════════════════
# BACKGROUND AUTO-SYNC THREAD
# ══════════════════════════════════════════════════════════════════
def start_calendar_auto_sync():
    """Run periodic background multi-calendar sync every 5 minutes."""
    def _run():
        while True:
            try:
                sync_from_google()
            except Exception:
                pass
            time.sleep(300)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

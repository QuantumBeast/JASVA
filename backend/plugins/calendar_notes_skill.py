"""
Calendar, Notes & Email Productivity Skill Plugin for JASVA.
Allows setting reminders, timers, daily agendas, managing quick notes, and launching calendar/email.
"""

import re
import time
import os
import webbrowser
import urllib.parse
from backend.sys_utils import load_notes, save_notes
from backend.memory_scheduler import add_schedule, get_active_schedules

import datetime
from backend.calendar_manager import (
    add_event, load_calendar_events, get_upcoming_agenda,
    get_events_for_date, export_to_ics
)

TRIGGERS = [
    r"^note:\s+",
    r"^add\s+note\s+",
    r"^show\s+notes",
    r"^clear\s+notes",
    r"^delete\s+note\s+\d+",
    r"^remind\s+me\s+",
    r"^set\s+reminder\s+",
    r"^set\s+timer\s+",
    r"^timer\s+",
    r"^agenda",
    r"^my\s+schedule",
    r"^calendar",
    r"^open\s+calendar",
    r"^open\s+email",
    r"^open\s+gmail",
    r"^open\s+outlook",
    r"^draft\s+email\s+",
    r"^email\s+",
    r"^schedule\s+",
    r"^add\s+event\s+",
    r"^export\s+calendar"
]

DESCRIPTION = "Manage quick notes, calendar events, daily agendas, reminders, timers, and email drafting."
PRIORITY = 22
ENABLED = True

def execute(text, context):
    lower = text.strip().lower()
    
    # 1. Open Calendar / Email Applications
    if lower in ("open calendar", "calendar", "launch calendar"):
        try:
            os.system("start outlookcal:")
        except Exception:
            webbrowser.open("https://calendar.google.com")
        return {"status": "success", "output": "Opening your calendar, sir."}
        
    if lower in ("open email", "open mail", "open gmail"):
        webbrowser.open("https://mail.google.com")
        return {"status": "success", "output": "Opening Gmail, sir."}

    if lower in ("open outlook", "launch outlook"):
        try:
            os.system("start outlookmail:")
        except Exception:
            webbrowser.open("https://outlook.live.com")
        return {"status": "success", "output": "Opening Outlook, sir."}

    # 2. Export Calendar
    if lower in ("export calendar", "export ics", "download calendar"):
        ics_path = export_to_ics()
        return {"status": "success", "output": f"Calendar exported to iCalendar format: {ics_path}"}

    # 3. Add Calendar Event / Schedule Meeting
    if lower.startswith("schedule ") or lower.startswith("add event "):
        # e.g. "schedule meeting with Team tomorrow at 3pm" or "add event sync on 2026-08-25 at 14:00"
        title = text.split(" ", 1)[-1].strip()
        ev_date = datetime.date.today().isoformat()
        ev_time = "09:00"

        # Check for tomorrow / today
        if "tomorrow" in lower:
            ev_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
            title = re.sub(r"\btomorrow\b", "", title, flags=re.IGNORECASE).strip()

        # Check for specific time like at 3pm, at 15:00
        time_match = re.search(r"\bat\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", title, re.IGNORECASE)
        if time_match:
            raw_time = time_match.group(1).strip()
            title = title[:time_match.start()] + title[time_match.end():]
            title = re.sub(r"\s+", " ", title).strip()
            try:
                if "am" in raw_time.lower() or "pm" in raw_time.lower():
                    parsed_t = datetime.datetime.strptime(raw_time.upper().replace(" ", ""), "%I:%M%p" if ":" in raw_time else "%I%p")
                else:
                    parsed_t = datetime.datetime.strptime(raw_time, "%H:%M")
                ev_time = parsed_t.strftime("%H:%M")
            except Exception:
                pass

        # Clean title
        title = re.sub(r"^(?:meeting\s+with\s+|event\s+|to\s+)", "", title, flags=re.IGNORECASE).strip()
        if not title:
            title = "Scheduled Event"

        event = add_event(title=title, event_date=ev_date, event_time=ev_time, category="MEET" if "meet" in lower else "WORK")
        return {"status": "success", "output": f"Event scheduled: '{event['title']}' on {event['date']} at {event['time']}."}

    # 4. Draft Email
    if lower.startswith("draft email ") or lower.startswith("email "):
        parts = text.split(" ", 2)
        body = parts[-1] if len(parts) > 2 else ""
        mail_url = f"mailto:?subject={urllib.parse.quote('From JARVIS')}&body={urllib.parse.quote(body)}"
        webbrowser.open(mail_url)
        return {"status": "success", "output": f"Opened email composer with draft content."}

    # 5. Add Note
    if lower.startswith("note: ") or lower.startswith("add note "):
        content = text.split(" ", 2)[-1].strip()
        notes = load_notes()
        notes.append(content)
        save_notes(notes)
        return {"status": "success", "output": f"Note recorded: '{content}'"}

    # 6. Clear / Delete Notes
    if lower in ("clear notes", "delete all notes"):
        save_notes([])
        return {"status": "success", "output": "All notes have been cleared, sir."}

    if lower.startswith("delete note "):
        nums = re.findall(r"\d+", lower)
        if nums:
            idx = int(nums[0]) - 1
            notes = load_notes()
            if 0 <= idx < len(notes):
                removed = notes.pop(idx)
                save_notes(notes)
                return {"status": "success", "output": f"Deleted note {idx + 1}: '{removed}'"}
            return {"status": "error", "output": f"Note number {idx + 1} not found."}

    # 7. Show Notes
    if lower in ("show notes", "notes", "list notes"):
        notes = load_notes()
        if not notes:
            return {"status": "success", "output": "Your notes list is currently empty, sir."}
        lines = [f"{i+1}. {n}" for i, n in enumerate(notes)]
        return {"status": "success", "output": "Your Saved Notes:\n" + "\n".join(lines)}

    # 8. Set Timers & Reminders
    if lower.startswith("remind me in ") or lower.startswith("set timer for ") or lower.startswith("timer for "):
        match_min = re.search(r"(\d+)\s*(?:min|minute)", lower)
        match_sec = re.search(r"(\d+)\s*(?:sec|second)", lower)
        match_hr = re.search(r"(\d+)\s*(?:hr|hour)", lower)
        
        delay_seconds = 0
        if match_min:
            delay_seconds += int(match_min.group(1)) * 60
        if match_sec:
            delay_seconds += int(match_sec.group(1))
        if match_hr:
            delay_seconds += int(match_hr.group(1)) * 3600

        if delay_seconds > 0:
            task_label = "Timer"
            if " to " in lower:
                task_label = text.split(" to ", 1)[-1].strip()
            elif " for " in lower:
                rem = lower.split(" for ", 1)[-1].strip()
                rem = re.sub(r"\d+\s*(?:minutes?|mins?|seconds?|secs?|hours?|hrs?)", "", rem).strip()
                if rem:
                    task_label = rem

            trigger_epoch = time.time() + delay_seconds
            time_str = time.strftime("%I:%M %p", time.localtime(trigger_epoch))
            add_schedule("timer", task_label, trigger_epoch)
            return {"status": "success", "output": f"Timer set for {delay_seconds // 60 if delay_seconds >= 60 else delay_seconds} {'minutes' if delay_seconds >= 60 else 'seconds'}: '{task_label}'."}

    # 9. Schedule / Agenda
    if "schedule" in lower or "agenda" in lower or "what's on my calendar" in lower:
        agenda = get_upcoming_agenda(limit=8)
        if not agenda:
            return {"status": "success", "output": "No upcoming events or reminders, sir."}
        lines = [f"• [{ev.get('date', '')} {ev.get('time', 'TBD')}] {ev.get('title', 'Event')}" for ev in agenda]
        return {"status": "success", "output": "Upcoming Agenda & Calendar:\n" + "\n".join(lines)}

    return None


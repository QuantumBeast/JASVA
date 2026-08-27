"""
proactive_engine.py — JASVA's proactive intelligence layer.
─────────────────────────────────────────────────────────────
Runs background monitors that trigger JASVA to speak first —
alerts, greetings, reminders, and system events — without the
user having to ask.

Components:
  1. Schedule/Timer notification speaker (fires alarms, timers)
  2. System event monitor (battery low, CPU spike, etc.)
  3. Contextual greeting engine (time-of-day, absence-based)
  4. Proactive delivery bridge (pushes events to frontend via JS eval)
"""

import os
import time
import json
import threading
import logging

logger = logging.getLogger("JASVA.proactive")

# ── Module-level state ──
_proactive_running = False
_proactive_thread = None
_api_ref = None  # Reference to JasvaAPI for JS bridge
_greeted_today = False
_last_interaction_time = 0

# Event priority levels
PRIORITY_CRITICAL = "critical"  # Speak immediately + persistent toast
PRIORITY_NORMAL = "normal"      # Speak + temporary toast
PRIORITY_LOW = "low"            # Log only, no speech


def set_api_ref(api):
    """Store a reference to the JasvaAPI so we can push events to the frontend."""
    global _api_ref
    _api_ref = api


def record_interaction():
    """Called whenever the user interacts with JASVA (chat, voice, etc.)."""
    global _last_interaction_time
    _last_interaction_time = time.time()


def _push_proactive_event(event_type, message, priority=PRIORITY_NORMAL, speak=True):
    """Push a proactive event to the frontend for rendering and optional TTS."""
    if not _api_ref:
        logger.debug(f"No API ref for proactive event: {message}")
        return

    payload = json.dumps({
        "type": event_type,
        "message": message,
        "priority": priority,
        "speak": speak,
        "timestamp": time.time(),
    })

    try:
        chat_win = _api_ref._windows.get("chat")
        if not chat_win:
            # Unified single window — try 'main'
            chat_win = _api_ref._windows.get("main")
        if chat_win:
            chat_win.evaluate_js(
                f"if(window.onProactiveEvent)window.onProactiveEvent({payload});"
            )
    except Exception as e:
        logger.debug(f"Proactive event push error: {e}")


def _check_schedule_notifications():
    """Check for fired schedule notifications and deliver them."""
    try:
        from backend.memory_scheduler import pop_unread_notifications
        notifications = pop_unread_notifications()
        if not notifications:
            return
        # Deliver recent unread notifications with natural speech phrasing
        for notif in notifications[-2:]:
            notif_type = notif.get("type", "info")
            title = notif.get("title", "")
            message = notif.get("message", notif.get("label", "")).strip()
            
            if notif_type in ["timer", "Timer"]:
                msg = f"Sir, your timer for {message} is up." if message and message.lower() != "timer" else "Sir, your timer is up."
                _push_proactive_event("timer", msg, PRIORITY_NORMAL, speak=True)
            elif notif_type in ["alarm", "alert"]:
                msg = f"Sir, your alarm for {message} is ringing." if message and message.lower() != "alarm" else "Sir, your alarm is ringing."
                _push_proactive_event("alarm", msg, PRIORITY_CRITICAL, speak=True)
            elif notif_type == "reminder":
                msg = f"Reminder: {message}" if message else "Scheduled reminder."
                _push_proactive_event("reminder", msg, PRIORITY_LOW, speak=False)
            else:
                text_to_speak = f"{title}. {message}".strip(". ")
                if text_to_speak:
                    _push_proactive_event("info", text_to_speak, PRIORITY_LOW, speak=False)
    except Exception as e:
        logger.debug(f"Schedule check error: {e}")


def _check_system_events():
    """Monitor system health and push alerts for notable events."""
    try:
        import psutil
    except ImportError:
        return

    try:
        # Battery monitoring (laptops only)
        battery = psutil.sensors_battery()
        if battery and not battery.power_plugged:
            pct = battery.percent
            if pct <= 10 and _should_fire("battery_critical"):
                _push_proactive_event(
                    "battery_critical",
                    f"Sir, battery is critically low at {pct}%. Please plug in.",
                    PRIORITY_CRITICAL,
                    speak=True
                )
            elif pct <= 20 and _should_fire("battery_low"):
                _push_proactive_event(
                    "battery_low",
                    f"Battery is at {pct}%.",
                    PRIORITY_LOW,
                    speak=False
                )

        # CPU spike detection
        cpu = psutil.cpu_percent(interval=1)
        if cpu > 92 and _should_fire("cpu_spike"):
            _push_proactive_event(
                "cpu_spike",
                f"CPU load at {cpu:.0f}%.",
                PRIORITY_LOW,
                speak=False,
            )

        # RAM pressure
        mem = psutil.virtual_memory()
        if mem.percent > 94 and _should_fire("ram_pressure"):
            _push_proactive_event(
                "ram_pressure",
                f"Memory usage is high at {mem.percent:.0f}%.",
                PRIORITY_LOW,
                speak=False
            )

    except Exception as e:
        logger.debug(f"System event check error: {e}")


def _check_contextual_greeting():
    """Deliver a time-aware greeting on first interaction after absence."""
    global _greeted_today, _last_interaction_time

    now = time.time()
    hour = time.localtime().tm_hour

    # Reset daily greeting flag at 4 AM
    if hour < 4:
        _greeted_today = False
        return

    if _greeted_today:
        return

    # Only greet if JASVA has been idle for > 2 hours (or just started)
    idle_duration = now - _last_interaction_time if _last_interaction_time else 99999
    if idle_duration < 7200:
        return

    # Build contextual greeting
    if 5 <= hour < 12:
        time_greeting = "Good morning"
    elif 12 <= hour < 17:
        time_greeting = "Good afternoon"
    elif 17 <= hour < 21:
        time_greeting = "Good evening"
    else:
        time_greeting = "Working late"

    # Try to get user's name from memory
    user_name = "sir"
    try:
        from backend.memory_scheduler import load_profile
        profile = load_profile()
        name = profile.get("identity", {}).get("name", "")
        if name:
            user_name = name
    except Exception:
        pass

    # Build full greeting
    parts = [f"{time_greeting}, {user_name}."]

    # Add weather if available
    try:
        from backend.ai_services import CACHED_WEATHER
        if CACHED_WEATHER and "Synchronizing" not in CACHED_WEATHER:
            parts.append(f"Current weather: {CACHED_WEATHER}.")
    except Exception:
        pass

    # Add pending schedules
    try:
        from backend.memory_scheduler import get_active_schedules
        schedules = get_active_schedules()
        if schedules:
            count = len(schedules)
            parts.append(
                f"You have {count} active {'reminder' if count == 1 else 'reminders'}."
            )
    except Exception:
        pass

    parts.append("All systems are online and operational.")

    greeting = " ".join(parts)
    _push_proactive_event("greeting", greeting, PRIORITY_NORMAL)
    _greeted_today = True
    _last_interaction_time = now


# ── Deduplication: prevent repeating the same alert type within N seconds ──
_recent_events = {}  # event_type -> last_time
_EVENT_DEDUP_WINDOW = 300  # 5 minutes


def _should_fire(event_type):
    """Check if this event type should fire (dedup window)."""
    now = time.time()
    last = _recent_events.get(event_type, 0)
    if now - last < _EVENT_DEDUP_WINDOW:
        return False
    _recent_events[event_type] = now
    return True


def _proactive_loop():
    """Main proactive monitoring loop — runs every 10 seconds."""
    global _proactive_running

    # Wait a bit after startup for windows to initialize
    time.sleep(8)

    # Initial greeting
    _check_contextual_greeting()

    tick = 0
    while _proactive_running:
        try:
            # Every tick (10s): check schedule notifications
            _check_schedule_notifications()

            # Every 6 ticks (60s): check system events
            if tick % 6 == 0:
                _check_system_events()

            # Every 30 ticks (5 min): re-check greeting (in case of long idle)
            if tick % 30 == 0:
                _check_contextual_greeting()

        except Exception as e:
            logger.error(f"Proactive loop error: {e}")

        tick += 1
        time.sleep(10)


def start_proactive_engine(api=None):
    """Start the proactive intelligence engine."""
    global _proactive_running, _proactive_thread
    if _proactive_running:
        return
    if api:
        set_api_ref(api)
    _proactive_running = True
    _proactive_thread = threading.Thread(target=_proactive_loop, daemon=True)
    _proactive_thread.start()
    logger.info("Proactive intelligence engine started.")


def stop_proactive_engine():
    """Stop the proactive intelligence engine."""
    global _proactive_running
    _proactive_running = False
    logger.info("Proactive intelligence engine stopped.")

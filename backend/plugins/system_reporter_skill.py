"""
Example JASVA Plugin — System Info Reporter
────────────────────────────────────────────
Demonstrates the plugin interface. This plugin responds to
"system report" / "system info" / "sys info" with a formatted summary
of CPU, memory, disk, and uptime.

To create your own plugin:
  1. Copy this file and rename it (e.g. my_feature.py)
  2. Define TRIGGERS, DESCRIPTION, and execute(text, context)
  3. Drop it into backend/plugins/ — JASVA loads it automatically on startup
"""

import platform
import time
import os

# ─── Required ─────────────────────────────────────────────
NAME = "System Reporter"
DESCRIPTION = "Shows a detailed system info report (CPU, RAM, disk, uptime)"
PRIORITY = 50          # lower = checked first (default 50)
ENABLED = True         # set False to skip without deleting the file

# Regex patterns — if ANY match the user's text, execute() is called
TRIGGERS = [
    r"\bsystem\s+report\b",
    r"\bsys(?:tem)?\s+info\b",
    r"\bfull\s+system\s+status\b",
]


def execute(text, context):
    """
    Called when a trigger matches.

    Args:
        text:    the full user input string
        context: dict with optional keys like 'window', 'config', etc.

    Returns:
        dict with at least {"status": "success"|"error", "output": "..."}
    """
    try:
        info_lines = []

        # OS details
        info_lines.append(f"**OS:** {platform.system()} {platform.release()} ({platform.version()})")
        info_lines.append(f"**Machine:** {platform.machine()}")
        info_lines.append(f"**Processor:** {platform.processor()}")
        info_lines.append(f"**Python:** {platform.python_version()}")

        # Memory (try psutil if available)
        try:
            import psutil
            mem = psutil.virtual_memory()
            info_lines.append(f"**RAM:** {mem.used // (1024**3):.1f} GB / {mem.total // (1024**3):.1f} GB ({mem.percent}% used)")
            cpu = psutil.cpu_percent(interval=0.5)
            info_lines.append(f"**CPU Usage:** {cpu}%")
            disk = psutil.disk_usage("/")
            info_lines.append(f"**Disk (C:):** {disk.used // (1024**3):.0f} GB / {disk.total // (1024**3):.0f} GB ({disk.percent}% used)")
            # Uptime
            boot_time = psutil.boot_time()
            uptime_sec = time.time() - boot_time
            hours, remainder = divmod(int(uptime_sec), 3600)
            minutes, _ = divmod(remainder, 60)
            info_lines.append(f"**Uptime:** {hours}h {minutes}m")
        except ImportError:
            info_lines.append("*(Install `psutil` for detailed CPU/RAM/disk stats)*")

        report = "\n".join(info_lines)
        return {
            "status": "success",
            "output": f"Here's your full system report, sir:\n\n{report}",
        }

    except Exception as e:
        return {
            "status": "error",
            "output": f"Failed to generate system report: {e}",
        }


# ─── Optional Hooks ───────────────────────────────────────
def on_load():
    """Called once when the plugin is loaded. Use for setup / warmup."""
    pass

def on_unload():
    """Called when JASVA is shutting down or the plugin is disabled."""
    pass

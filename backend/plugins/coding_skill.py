"""
Coding Skill Plugin for JASVA.
Allows executing python/powershell scripts, inspecting codebase files, and running terminal commands.
"""

import os
import subprocess
from backend.sys_utils import ROOT_DIR, CREATE_NO_WINDOW

TRIGGERS = [
    r"^run\s+python\s+",
    r"^run\s+code\s+",
    r"^exec\s+",
    r"^eval\s+",
    r"^powershell\s+",
    r"^run\s+cmd\s+",
]

DESCRIPTION = "Execute Python and PowerShell code, run scripts, and inspect system code."
PRIORITY = 20
ENABLED = True

def execute(text, context):
    lower = text.strip().lower()
    
    # Run python snippet
    if lower.startswith("run python ") or lower.startswith("run code ") or lower.startswith("eval "):
        code = text.split(" ", 2)[-1].strip()
        try:
            res = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=CREATE_NO_WINDOW
            )
            out = (res.stdout or res.stderr or "Code executed successfully with no output.").strip()
            return {"status": "success", "output": f"Python Output:\n{out}"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "output": "Execution timed out (15s limit)."}
        except Exception as e:
            return {"status": "error", "output": f"Execution error: {str(e)}"}
            
    # Run powershell command
    if lower.startswith("powershell ") or lower.startswith("run cmd "):
        cmd = text.split(" ", 1)[1].strip()
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=CREATE_NO_WINDOW
            )
            out = (res.stdout or res.stderr or "Command executed with no output.").strip()
            return {"status": "success", "output": f"PowerShell Output:\n{out}"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "output": "Command timed out (15s limit)."}
        except Exception as e:
            return {"status": "error", "output": f"PowerShell error: {str(e)}"}

    return {"status": "error", "output": "Unrecognized coding skill command."}

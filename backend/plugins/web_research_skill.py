"""
Web Research Skill Plugin for JASVA.
Performs web queries, scrapes URLs, and extracts key facts.
"""

import urllib.request
import urllib.parse
import json
import re

TRIGGERS = [
    r"^search\s+for\s+",
    r"^search\s+web\s+",
    r"^google\s+",
    r"^scrape\s+",
    r"^read\s+url\s+",
]

DESCRIPTION = "Autonomous web search, URL fetching, and online research."
PRIORITY = 25
ENABLED = True

def execute(text, context):
    lower = text.strip().lower()
    
    # URL reader / scraper
    if lower.startswith("scrape ") or lower.startswith("read url "):
        url = text.split(" ", 1)[1].strip()
        if not url.startswith("http"):
            url = "https://" + url
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            # Strip tags
            cleaned = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.IGNORECASE)
            cleaned = re.sub(r'<style[\s\S]*?</style>', ' ', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            summary = cleaned[:800] + ("..." if len(cleaned) > 800 else "")
            return {"status": "success", "output": f"Web Content from {url}:\n\n{summary}"}
        except Exception as e:
            return {"status": "error", "output": f"Failed to read URL: {str(e)}"}
            
    # Web search
    query = text
    for prefix in ["search for ", "search web ", "google "]:
        if lower.startswith(prefix):
            query = text[len(prefix):].strip()
            break
            
    try:
        from backend.ai_services import search_duckduckgo
        results = search_duckduckgo(query)
        if results:
            lines = []
            for r in results[:4]:
                lines.append(f"• {r.get('title', 'Result')}: {r.get('snippet', '')} ({r.get('url', '')})")
            return {"status": "success", "output": f"Search Results for '{query}':\n\n" + "\n\n".join(lines)}
    except Exception:
        pass
        
    return {"status": "success", "output": f"Query '{query}' processed."}

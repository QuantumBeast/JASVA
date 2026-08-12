import os
import sys
import json
import time
import uuid
import threading
import ctypes
from datetime import datetime, timedelta

# Import from sys_utils
from backend.sys_utils import (
    DB_DIR, load_config, MEMORYSTATUSEX,
    load_memory_db, save_memory_db
)

# Core Memory & Profile Configuration
MAX_HISTORY = 50
KEEP_RECENT = 20

def _default_profile():
    return {
        "identity": {},
        "preferences": {},
        "relationships": [],
        "habits": [],
        "interests": [],
        "facts": [],
        "dislikes": [],
    }

# ──────────────────────────────────────────────────────────────
# Profile Operations
# ──────────────────────────────────────────────────────────────
def load_profile():
    db = load_memory_db()
    profile = db.get("profile", _default_profile())
    default = _default_profile()
    for key in default:
        if key not in profile:
            profile[key] = default[key]
    return profile

def save_profile(profile):
    db = load_memory_db()
    db["profile"] = profile
    save_memory_db(db)

def update_identity(key, value):
    profile = load_profile()
    profile["identity"][key] = value
    save_profile(profile)

def add_preference(key, value):
    profile = load_profile()
    profile["preferences"][key] = value
    save_profile(profile)

def add_relationship(name, relation):
    profile = load_profile()
    existing = [r for r in profile["relationships"] if r.get("name", "").lower() == name.lower()]
    if existing:
        existing[0]["relation"] = relation
    else:
        profile["relationships"].append({"name": name, "relation": relation})
    save_profile(profile)

def add_habit(pattern):
    profile = load_profile()
    existing_patterns = [h.get("pattern", "").lower() for h in profile["habits"]]
    if pattern.lower() not in existing_patterns:
        profile["habits"].append({
            "pattern": pattern,
            "noted_at": time.time()
        })
        profile["habits"] = profile["habits"][-20:]
        save_profile(profile)

def add_interest(interest):
    profile = load_profile()
    existing_lower = [i.lower() for i in profile["interests"]]
    if interest.lower() not in existing_lower:
        profile["interests"].append(interest)
        profile["interests"] = profile["interests"][-30:]
        save_profile(profile)

def add_fact(fact):
    profile = load_profile()
    existing_lower = [f.lower() for f in profile["facts"]]
    if fact.lower() not in existing_lower:
        profile["facts"].append(fact)
        profile["facts"] = profile["facts"][-50:]
        save_profile(profile)

def add_dislike(dislike):
    profile = load_profile()
    existing_lower = [d.lower() for d in profile["dislikes"]]
    if dislike.lower() not in existing_lower:
        profile["dislikes"].append(dislike)
        profile["dislikes"] = profile["dislikes"][-20:]
        save_profile(profile)

def forget_about(target):
    profile = load_profile()
    target_lower = target.lower()
    removed = False
    keys_to_remove = [k for k, v in profile["identity"].items() if target_lower in str(v).lower() or target_lower in k.lower()]
    for k in keys_to_remove:
        del profile["identity"][k]
        removed = True
    keys_to_remove = [k for k, v in profile["preferences"].items() if target_lower in str(v).lower() or target_lower in k.lower()]
    for k in keys_to_remove:
        del profile["preferences"][k]
        removed = True
    original_len = len(profile["relationships"])
    profile["relationships"] = [r for r in profile["relationships"] if target_lower not in r.get("name", "").lower() and target_lower not in r.get("relation", "").lower()]
    if len(profile["relationships"]) < original_len:
        removed = True
    original_len = len(profile["habits"])
    profile["habits"] = [h for h in profile["habits"] if target_lower not in h.get("pattern", "").lower()]
    if len(profile["habits"]) < original_len:
        removed = True
    original_len = len(profile["interests"])
    profile["interests"] = [i for i in profile["interests"] if target_lower not in i.lower()]
    if len(profile["interests"]) < original_len:
        removed = True
    original_len = len(profile["facts"])
    profile["facts"] = [f for f in profile["facts"] if target_lower not in f.lower()]
    if len(profile["facts"]) < original_len:
        removed = True
    original_len = len(profile["dislikes"])
    profile["dislikes"] = [d for d in profile["dislikes"] if target_lower not in d.lower()]
    if len(profile["dislikes"]) < original_len:
        removed = True
    save_profile(profile)
    return removed

def clear_all_memory():
    save_profile(_default_profile())
    _save_json(SUMMARIES_FILE, [])

def process_memory_updates(updates):
    if not updates or not isinstance(updates, list):
        return
    for update in updates:
        if not isinstance(update, dict):
            continue
        update_type = update.get("type", "").lower()
        try:
            if update_type == "identity":
                key = update.get("key", "")
                value = update.get("value", "")
                if key and value: update_identity(key, value)
            elif update_type == "preference":
                key = update.get("key", "")
                value = update.get("value", "")
                if key and value: add_preference(key, value)
            elif update_type == "relationship":
                name = update.get("name", "")
                relation = update.get("relation", "")
                if name and relation: add_relationship(name, relation)
            elif update_type == "habit":
                pattern = update.get("pattern", "")
                if pattern: add_habit(pattern)
            elif update_type == "interest":
                value = update.get("value", "")
                if value: add_interest(value)
            elif update_type == "fact":
                value = update.get("value", "")
                if value: add_fact(value)
            elif update_type == "dislike":
                value = update.get("value", "")
                if value: add_dislike(value)
            elif update_type == "learn_command":
                trigger = update.get("trigger", "")
                commands_list = update.get("commands", [])
                description = update.get("description", "")
                if isinstance(commands_list, str): commands_list = [commands_list]
                if trigger and commands_list: add_custom_skill(trigger, commands_list, description)
            elif update_type == "forget_command":
                trigger = update.get("trigger", "")
                if trigger: remove_custom_skill(trigger)
        except Exception:
            continue

def get_user_profile_string():
    profile = load_profile()
    sections = []
    if profile["identity"]:
        identity_parts = [f"{key}: {value}" for key, value in profile["identity"].items()]
        if identity_parts: sections.append("User Identity: " + ", ".join(identity_parts))
    if profile["preferences"]:
        pref_parts = [f"their favorite {key} is {value}" for key, value in profile["preferences"].items()]
        if pref_parts: sections.append("Preferences: " + ", ".join(pref_parts))
    if profile["relationships"]:
        rel_parts = [f"{r['name']} ({r['relation']})" for r in profile["relationships"]]
        sections.append("People they've mentioned: " + ", ".join(rel_parts))
    if profile["interests"]:
        sections.append("Interests: " + ", ".join(profile["interests"]))
    if profile["habits"]:
        habit_parts = [h["pattern"] for h in profile["habits"][-10:]]
        sections.append("Known habits/patterns: " + "; ".join(habit_parts))
    if profile["facts"]:
        sections.append("Other facts: " + "; ".join(profile["facts"][-15:]))
    if profile["dislikes"]:
        sections.append("Dislikes: " + ", ".join(profile["dislikes"]))
    if not sections:
        return ""
    return "\n\nWhat you know about the user (use this to personalize naturally):\n" + "\n".join(f"- {s}" for s in sections)

# ──────────────────────────────────────────────────────────────
# Chat Memory & History (Semantic Search via TF-IDF)
# ──────────────────────────────────────────────────────────────
def _build_memory_corpus(profile):
    """Build a list of (text, label) tuples from the entire user profile with semantic expansion tags."""
    corpus = []
    
    # Simple synonym mapping for semantic expansion
    synonyms = {
        "music": "songs song artist singer playlist track audio melody tune sound",
        "job": "work occupation career profession job employment industry employee company living office business",
        "work": "job occupation career profession job employment industry employee company living office business",
        "home": "house live residence address hometown city place stay flat apartment",
        "food": "eat meal dinner lunch breakfast cooking recipe dish cuisine restaurant taste",
        "hobby": "interest leisure pass time recreation activity favorite like love enjoy",
        "pet": "dog cat animal puppy kitten vet breed",
        "relation": "family friend parent mom dad mother father sister brother cousin relative child son daughter husband wife"
    }

    def expand_text(text):
        lower = text.lower()
        expanded = [text]
        for term, syns in synonyms.items():
            if term in lower:
                expanded.append(syns)
        return " ".join(expanded)

    for key, value in profile.get("identity", {}).items():
        doc_text = expand_text(f"{key} {value} identity details profile self")
        corpus.append((doc_text, f"{key}: {value}"))
        
    for key, value in profile.get("preferences", {}).items():
        doc_text = expand_text(f"preference key_{key} {key} {value} likes loves favorite enjoys custom prefers")
        corpus.append((doc_text, f"Prefers {key}: {value}"))
        
    for rel in profile.get("relationships", []):
        name = rel.get("name", "")
        relation = rel.get("relation", "")
        doc_text = expand_text(f"relationship relation {name} {relation} person family friend contact name")
        corpus.append((doc_text, f"{name} is their {relation}"))
        
    for habit in profile.get("habits", []):
        pattern = habit.get("pattern", "")
        doc_text = expand_text(f"habit routine schedule daily loop behavior repeat custom {pattern}")
        corpus.append((doc_text, f"Habit: {pattern}"))
        
    for interest in profile.get("interests", []):
        doc_text = expand_text(f"interest hobby hobbies likes loves passionate about active enthusiastic {interest}")
        corpus.append((doc_text, f"Interested in {interest}"))
        
    for fact in profile.get("facts", []):
        doc_text = expand_text(f"fact knowledge information memory truth detail {fact}")
        corpus.append((doc_text, fact))
        
    for dislike in profile.get("dislikes", []):
        doc_text = expand_text(f"dislike hate avoid dislike allergy not_like unhappy {dislike}")
        corpus.append((doc_text, f"Dislikes: {dislike}"))
        
    return corpus


def get_relevant_context(query, top_k=10):
    """Retrieve the most semantically relevant memories using TF-IDF cosine similarity."""
    from backend.nlp_engine import TFIDFVectorizer
    profile = load_profile()
    corpus = _build_memory_corpus(profile)
    if not corpus:
        return []

    # Also include conversation summaries for richer recall
    summaries = load_conversation_summaries()
    for s in summaries[-10:]:
        text = s.get("summary", "")
        if text:
            corpus.append((f"conversation {text}", f"Past conversation: {text}"))

    # Build TF-IDF index
    vectorizer = TFIDFVectorizer()
    doc_texts = [item[0] for item in corpus]
    vectorizer.fit(doc_texts)

    # Vectorize query
    query_vec = vectorizer.transform(query)
    if not query_vec:
        # Fallback to keyword matching if query is too short for TF-IDF
        query_words = set(query.lower().split())
        results = []
        for doc_text, label in corpus:
            overlap = len(query_words & set(doc_text.lower().split()))
            if overlap > 0:
                results.append((overlap, label))
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:top_k]]

    # Score each memory by cosine similarity
    scored = []
    for i, (doc_text, label) in enumerate(corpus):
        doc_vec = vectorizer.transform(doc_text)
        sim = TFIDFVectorizer.cosine_similarity(query_vec, doc_vec)
        if sim > 0.05:  # Threshold to avoid noise
            # Apply temporal decay for conversation summaries
            decay = 1.0
            if label.startswith("Past conversation:") and i >= len(corpus) - len(summaries):
                # More recent summaries get higher weight
                recency = (i - (len(corpus) - len(summaries))) / max(len(summaries), 1)
                decay = 0.7 + 0.3 * recency
            scored.append((sim * decay, label))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in scored[:top_k]]

def load_chat_history():
    db = load_memory_db()
    return db.get("history") or []

def save_chat_history(history):
    db = load_memory_db()
    db["history"] = history[-MAX_HISTORY:]
    save_memory_db(db)

def add_to_chat_history(role, content):
    if not content: return
    history = load_chat_history()
    if history and history[-1]["role"] == role and history[-1]["content"] == content: return
    history.append({"role": role, "content": content})
    save_chat_history(history)

def get_history_for_prompt():
    history = load_chat_history()
    summaries = load_conversation_summaries()
    result_messages = []
    if summaries:
        summary_text = "Summary of earlier conversations:\n"
        for s in summaries[-5:]:
            summary_text += f"- {s.get('summary', '')}\n"
        result_messages.append({"role": "user", "content": summary_text})
        result_messages.append({"role": "assistant", "content": "I remember our past conversations. What would you like to talk about?"})
    result_messages.extend(history)
    return result_messages

def load_conversation_summaries():
    db = load_memory_db()
    return db.get("summaries", [])

def save_conversation_summaries(summaries):
    db = load_memory_db()
    db["summaries"] = summaries[-20:]
    save_memory_db(db)

def add_conversation_summary(summary_text):
    summaries = load_conversation_summaries()
    summaries.append({
        "summary": summary_text,
        "timestamp": time.time()
    })
    save_conversation_summaries(summaries)

def should_summarize():
    history = load_chat_history()
    return len(history) >= MAX_HISTORY

def compress_history(summary_text):
    add_conversation_summary(summary_text)
    history = load_chat_history()
    recent = history[-KEEP_RECENT:]
    db = load_memory_db()
    db["history"] = recent
    save_memory_db(db)

def migrate_legacy_facts():
    db = load_memory_db()
    legacy_facts = db.get("facts") or []
    if not legacy_facts: return
    profile = load_profile()
    for fact in legacy_facts:
        if fact.lower() not in [f.lower() for f in profile["facts"]]:
            profile["facts"].append(fact)
    save_profile(profile)
    db["facts"] = []
    save_memory_db(db)

def get_memory_stats():
    profile = load_profile()
    history = load_chat_history()
    summaries = load_conversation_summaries()
    total_facts = (
        len(profile["identity"]) +
        len(profile["preferences"]) +
        len(profile["relationships"]) +
        len(profile["habits"]) +
        len(profile["interests"]) +
        len(profile["facts"]) +
        len(profile["dislikes"])
    )
    return {
        "total_memories": total_facts,
        "identity_fields": len(profile["identity"]),
        "preferences": len(profile["preferences"]),
        "relationships": len(profile["relationships"]),
        "interests": len(profile["interests"]),
        "habits": len(profile["habits"]),
        "facts": len(profile["facts"]),
        "chat_history_length": len(history),
        "conversation_summaries": len(summaries)
    }

def export_memory_data():
    try:
        export_data = {
            "profile": load_profile(),
            "memory_db": load_memory_db(),
            "chat_history": load_chat_history(),
            "summaries": load_conversation_summaries(),
            "export_timestamp": time.time(),
            "export_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        export_file = os.path.join(DB_DIR, f"memory_export_{int(time.time())}.json")
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        return {"status": "success", "file": export_file}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def import_memory_data(export_file):
    try:
        if not os.path.exists(export_file):
            return {"status": "error", "message": "Export file not found"}
        with open(export_file, "r", encoding="utf-8") as f:
            import_data = json.load(f)
        required_keys = ["profile", "memory_db", "chat_history", "summaries"]
        for key in required_keys:
            if key not in import_data:
                return {"status": "error", "message": f"Invalid export file: missing {key}"}
        export_memory_data()
        
        # Save all imported keys in one write
        db = load_memory_db()
        db["profile"] = import_data["profile"]
        db["history"] = import_data["chat_history"]
        db["summaries"] = import_data["summaries"]
        save_memory_db(db)
        return {"status": "success", "message": "Memory data imported successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def delete_memory_data(category=None, key=None):
    try:
        if category is None:
            save_profile(_default_profile())
            save_memory_db({})
            save_chat_history([])
            save_conversation_summaries([])
            return {"status": "success", "message": "All memory data deleted"}
        profile = load_profile()
        if category == "identity":
            if key:
                if key in profile.get("identity", {}):
                    del profile["identity"][key]
                    save_profile(profile)
                    return {"status": "success", "message": f"Identity field '{key}' deleted"}
                return {"status": "error", "message": f"Identity field '{key}' not found"}
            profile["identity"] = {}
            save_profile(profile)
            return {"status": "success", "message": "All identity data deleted"}
        elif category == "preferences":
            if key:
                if key in profile.get("preferences", {}):
                    del profile["preferences"][key]
                    save_profile(profile)
                    return {"status": "success", "message": f"Preference '{key}' deleted"}
                return {"status": "error", "message": f"Preference '{key}' not found"}
            profile["preferences"] = {}
            save_profile(profile)
            return {"status": "success", "message": "All preferences deleted"}
        elif category == "relationships":
            if key:
                profile["relationships"] = [r for r in profile.get("relationships", []) if r.get("name") != key]
                save_profile(profile)
                return {"status": "success", "message": f"Relationship '{key}' deleted"}
            profile["relationships"] = []
            save_profile(profile)
            return {"status": "success", "message": "All relationships deleted"}
        elif category == "interests":
            if key:
                profile["interests"] = [i for i in profile.get("interests", []) if i != key]
                save_profile(profile)
                return {"status": "success", "message": f"Interest '{key}' deleted"}
            profile["interests"] = []
            save_profile(profile)
            return {"status": "success", "message": "All interests deleted"}
        elif category == "habits":
            if key:
                profile["habits"] = [h for h in profile.get("habits", []) if h.get("pattern") != key]
                save_profile(profile)
                return {"status": "success", "message": f"Habit '{key}' deleted"}
            profile["habits"] = []
            save_profile(profile)
            return {"status": "success", "message": "All habits deleted"}
        elif category == "facts":
            if key:
                profile["facts"] = [f for f in profile.get("facts", []) if f != key]
                save_profile(profile)
                return {"status": "success", "message": f"Fact '{key}' deleted"}
            profile["facts"] = []
            save_profile(profile)
            return {"status": "success", "message": "All facts deleted"}
        elif category == "chat_history":
            chat_history = load_chat_history()
            if key:
                try:
                    index = int(key)
                    if 0 <= index < len(chat_history):
                        chat_history.pop(index)
                        save_chat_history(chat_history)
                        return {"status": "success", "message": f"Chat message at index {index} deleted"}
                    return {"status": "error", "message": f"Invalid index {index}"}
                except ValueError:
                    return {"status": "error", "message": "Invalid index format"}
            save_chat_history([])
            return {"status": "success", "message": "All chat history deleted"}
        return {"status": "error", "message": f"Unknown category: {category}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ──────────────────────────────────────────────────────────────
# Custom Command Macros / Skills
# ──────────────────────────────────────────────────────────────
def load_custom_skills():
    db = load_memory_db()
    return db.get("custom_skills", [])

def save_custom_skills(skills):
    db = load_memory_db()
    db["custom_skills"] = skills
    save_memory_db(db)

def add_custom_skill(trigger, commands_list, description=""):
    skills = load_custom_skills()
    trigger_clean = trigger.strip().lower()
    skills = [s for s in skills if s.get("trigger", "").lower() != trigger_clean]
    skills.append({
        "trigger": trigger_clean,
        "commands": commands_list,
        "description": description,
        "created_at": time.time()
    })
    save_custom_skills(skills)

def remove_custom_skill(trigger):
    skills = load_custom_skills()
    trigger_clean = trigger.strip().lower()
    skills = [s for s in skills if s.get("trigger", "").lower() != trigger_clean]
    save_custom_skills(skills)

# Migrate legacy formats if necessary
migrate_legacy_facts()

# ──────────────────────────────────────────────────────────────
# Emotional State Machine
# ──────────────────────────────────────────────────────────────
_MOOD_TRANSITIONS = {
    # user_emotion → (jasva_mood, energy_delta, rapport_delta)
    "happy":     ("happy",      +0.1, +0.05),
    "positive":  ("happy",      +0.05, +0.03),
    "excited":   ("excited",    +0.15, +0.05),
    "grateful":  ("happy",      +0.05, +0.08),
    "neutral":   ("calm",        0.0,   0.0),
    "negative":  ("concerned",  -0.05, -0.02),
    "sad":       ("empathetic", -0.1,  +0.03),
    "angry":     ("concerned",  -0.1,  -0.05),
    "anxious":   ("supportive", -0.05, +0.02),
    "tired":     ("gentle",     -0.05, +0.02),
    "bored":     ("energetic",  +0.05,  0.0),
    "distressed":("empathetic", -0.15, +0.05),
}


class EmotionalStateManager:
    """Manages JASVA's persistent emotional/cognitive state.
    
    The mood evolves naturally based on:
    - User sentiment from NLP analysis
    - Time gap between interactions
    - Rapport built over repeated conversations
    """

    @staticmethod
    def load_state():
        db = load_memory_db()
        return db.get("cognitive_state", {
            "mood": "calm",
            "energy_level": 0.7,
            "rapport_score": 0.5,
            "last_interaction_time": 0,
            "interaction_count": 0,
            "mood_history": []
        })

    @staticmethod
    def save_state(state):
        db = load_memory_db()
        db["cognitive_state"] = state
        save_memory_db(db)

    @classmethod
    def update_from_sentiment(cls, sentiment_analysis):
        """Update JASVA's mood based on user's detected sentiment."""
        state = cls.load_state()
        user_emotion = sentiment_analysis.get("dominant_emotion", "neutral")
        valence = sentiment_analysis.get("valence", 0.0)

        # Look up mood transition
        transition = _MOOD_TRANSITIONS.get(user_emotion, ("calm", 0.0, 0.0))
        new_mood, energy_delta, rapport_delta = transition

        # Update energy level (bounded 0-1)
        state["energy_level"] = max(0.0, min(1.0, state.get("energy_level", 0.7) + energy_delta))

        # Update rapport score (bounded 0-1)
        state["rapport_score"] = max(0.0, min(1.0, state.get("rapport_score", 0.5) + rapport_delta))

        # Set mood
        state["mood"] = new_mood

        # Track interaction timing
        now = time.time()
        last_time = state.get("last_interaction_time", 0)
        gap_hours = (now - last_time) / 3600 if last_time > 0 else 0

        # Long gap adjustments
        if gap_hours > 12:
            state["energy_level"] = 0.7  # Reset energy after long absence
            state["mood"] = "warm"  # Warm welcome mood
        elif gap_hours > 4:
            state["energy_level"] = max(0.5, state["energy_level"])

        state["last_interaction_time"] = now
        state["interaction_count"] = state.get("interaction_count", 0) + 1

        # Keep mood history (last 20 entries)
        mood_history = state.get("mood_history", [])
        mood_history.append({
            "mood": new_mood,
            "user_emotion": user_emotion,
            "valence": valence,
            "timestamp": now
        })
        state["mood_history"] = mood_history[-20:]

        cls.save_state(state)
        return state

    @classmethod
    def get_mood_context(cls):
        """Generate a mood context string for the system prompt."""
        state = cls.load_state()
        mood = state.get("mood", "calm")
        energy = state.get("energy_level", 0.7)
        rapport = state.get("rapport_score", 0.5)
        count = state.get("interaction_count", 0)
        last_time = state.get("last_interaction_time", 0)

        # Compute interaction gap
        gap_hours = (time.time() - last_time) / 3600 if last_time > 0 else 0

        parts = [f"\nYour current emotional state:"]
        parts.append(f"- Mood: {mood}")
        parts.append(f"- Energy level: {'high' if energy > 0.7 else 'moderate' if energy > 0.4 else 'low'}")
        parts.append(f"- Rapport with user: {'strong' if rapport > 0.7 else 'developing' if rapport > 0.4 else 'new'}")

        if gap_hours > 12:
            parts.append(f"- Note: It has been {int(gap_hours)} hours since the last interaction. Greet warmly.")
        elif gap_hours > 4:
            parts.append(f"- Note: It has been a while ({int(gap_hours)} hours). Be welcoming.")

        if count > 50:
            parts.append("- You and the user have had many conversations. You know each other well.")
        elif count > 10:
            parts.append("- You're getting to know the user. Be attentive and build rapport.")

        # Mood-specific tone instructions
        tone_map = {
            "happy": "Match their positive energy. Be upbeat and encouraging.",
            "excited": "Be enthusiastic and share their excitement!",
            "concerned": "Be gentle and supportive. Acknowledge their frustration without being patronizing.",
            "empathetic": "Show genuine care. Listen actively and validate their feelings before offering help.",
            "supportive": "Be reassuring and calm. Help them feel less anxious.",
            "gentle": "Keep your tone soft and considerate. They may be low on energy.",
            "energetic": "Bring some energy! Suggest fun activities or interesting topics.",
            "warm": "Welcome them back warmly. Show you noticed their absence.",
            "calm": "Be your steady, helpful self.",
        }
        if mood in tone_map:
            parts.append(f"- Tone guidance: {tone_map[mood]}")

        return "\n".join(parts)


# ──────────────────────────────────────────────────────────────
# Scheduler and Alarms
# ──────────────────────────────────────────────────────────────
_scheduler_thread = None
_scheduler_running = False
_active_timers = {}
_lock = threading.Lock()
_last_greeting_date = None
_last_battery_warn = 0
_last_resource_warn = 0

def load_schedules():
    db = load_memory_db()
    return db.get("schedules", [])

def save_schedules(schedules):
    db = load_memory_db()
    db["schedules"] = schedules
    save_memory_db(db)

def add_schedule(schedule_type, label, trigger_time, command=None, recurring=None):
    schedules = load_schedules()
    entry = {
        "id": str(uuid.uuid4())[:8],
        "type": schedule_type,
        "label": label,
        "trigger_time": trigger_time,
        "command": command,
        "recurring": recurring,
        "created_at": time.time(),
        "fired": False
    }
    schedules.append(entry)
    save_schedules(schedules)
    _register_timer(entry)
    return entry

def remove_schedule(schedule_id):
    schedules = load_schedules()
    original_len = len(schedules)
    schedules = [s for s in schedules if s["id"] != schedule_id]
    if len(schedules) < original_len:
        save_schedules(schedules)
        with _lock:
            if schedule_id in _active_timers:
                _active_timers[schedule_id].cancel()
                del _active_timers[schedule_id]
        return True
    return False

def get_active_schedules():
    schedules = load_schedules()
    return [s for s in schedules if not s.get("fired", False)]

def clear_all_schedules():
    with _lock:
        for timer in _active_timers.values():
            timer.cancel()
        _active_timers.clear()
    save_schedules([])

def load_notifications():
    db = load_memory_db()
    return db.get("notifications", [])

def save_notifications(notifications):
    db = load_memory_db()
    db["notifications"] = notifications
    save_memory_db(db)

def push_notification(title, message, notif_type="info", command=None):
    notifications = load_notifications()
    notifications.append({
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "message": message,
        "type": notif_type,
        "command": command,
        "timestamp": time.time(),
        "read": False
    })
    notifications = notifications[-50:]
    save_notifications(notifications)

def pop_unread_notifications():
    notifications = load_notifications()
    unread = [n for n in notifications if not n.get("read", False)]
    for n in notifications:
        n["read"] = True
    save_notifications(notifications)
    return unread

def clear_notifications():
    save_notifications([])

def _register_timer(entry):
    delay = entry["trigger_time"] - time.time()
    if delay <= 0:
        _on_timer_fire(entry["id"])
        return
    timer = threading.Timer(delay, _on_timer_fire, args=[entry["id"]])
    timer.daemon = True
    with _lock:
        _active_timers[entry["id"]] = timer
    timer.start()

def _on_timer_fire(schedule_id):
    schedules = load_schedules()
    entry = None
    for s in schedules:
        if s["id"] == schedule_id:
            entry = s
            break
    if not entry: return
    entry["fired"] = True
    save_schedules(schedules)
    with _lock:
        _active_timers.pop(schedule_id, None)
    stype = entry.get("type", "timer")
    label = entry.get("label", "Timer")
    if stype == "timer":
        push_notification("⏱️ Timer Complete", f"{label}", "timer", entry.get("command"))
    elif stype == "alarm":
        push_notification("⏰ Alarm", f"{label}", "alert", entry.get("command"))
    elif stype == "reminder":
        push_notification("📌 Reminder", f"{label}", "reminder", entry.get("command"))
    elif stype == "scheduled_command":
        push_notification("🤖 Scheduled Task", f"{label}", "info", entry.get("command"))
    if entry.get("recurring"):
        interval = entry["recurring"].get("interval_seconds", 0)
        if interval > 0:
            add_schedule(entry["type"], entry["label"], time.time() + interval, entry.get("command"), entry.get("recurring"))

def _get_battery_info():
    try:
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]
        status = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            percent = status.BatteryLifePercent
            is_charging = status.ACLineStatus == 1
            if percent <= 100: return percent, is_charging
    except Exception:
        pass
    return None, None

def _get_time_greeting():
    hour = datetime.now().hour
    if 5 <= hour < 12: return "Good morning"
    elif 12 <= hour < 17: return "Good afternoon"
    elif 17 <= hour < 21: return "Good evening"
    return "Hey there, night owl"

def _proactive_monitor():
    from backend.sys_utils import logger
    global _last_greeting_date, _last_battery_warn, _last_resource_warn
    while _scheduler_running:
        try:
            now = time.time()
            today = datetime.now().date()
            if _last_greeting_date != today:
                greeting = _get_time_greeting()
                _last_greeting_date = today
                push_notification(f"👋 {greeting}!", "JASVA is online and ready to assist you.", "info")
            battery_pct, is_charging = _get_battery_info()
            if battery_pct is not None and battery_pct <= 20 and not is_charging:
                if now - _last_battery_warn > 600:
                    _last_battery_warn = now
                    push_notification("🔋 Low Battery Warning", f"Battery is at {battery_pct}%. You should plug in soon.", "warning")
            try:
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(stat)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    ram_pct = stat.dwMemoryLoad
                    if ram_pct >= 90 and now - _last_resource_warn > 300:
                        _last_resource_warn = now
                        push_notification("⚠️ High Memory Usage", f"RAM usage is at {ram_pct}%. Consider closing some applications.", "warning")
            except Exception:
                pass
        except Exception:
            pass
        for _ in range(30):
            if not _scheduler_running: break
            time.sleep(1)

def start_scheduler():
    global _scheduler_thread, _scheduler_running
    if _scheduler_running: return
    _scheduler_running = True
    schedules = load_schedules()
    now = time.time()
    schedules = [s for s in schedules if not (s.get("fired", False) and now - s.get("trigger_time", 0) > 86400)]
    for entry in schedules:
        if not entry.get("fired", False):
            if entry["trigger_time"] > now:
                _register_timer(entry)
            else:
                entry["fired"] = True
                push_notification("⏱️ Missed Schedule", f"You missed: {entry.get('label', 'Unknown')} (was due while JASVA was offline)", "info", entry.get("command"))
    save_schedules(schedules)
    _scheduler_thread = threading.Thread(target=_proactive_monitor, daemon=True)
    _scheduler_thread.start()

def stop_scheduler():
    global _scheduler_running
    _scheduler_running = False
    with _lock:
        for timer in _active_timers.values():
            timer.cancel()
        _active_timers.clear()

def parse_duration(text):
    import re
    text = text.lower().strip()
    total = 0
    found = False
    h_match = re.search(r'(\d+)\s*(?:hours?|hrs?|h)\b', text)
    if h_match:
        total += int(h_match.group(1)) * 3600
        found = True
    m_match = re.search(r'(\d+)\s*(?:minutes?|mins?|m)\b', text)
    if m_match:
        total += int(m_match.group(1)) * 60
        found = True
    s_match = re.search(r'(\d+)\s*(?:seconds?|secs?|s)\b', text)
    if s_match:
        total += int(s_match.group(1))
        found = True
    if not found:
        num_match = re.search(r'(\d+)', text)
        if num_match:
            total = int(num_match.group(1)) * 60
            found = True
    return total if found else None

def parse_time_of_day(text):
    import re
    text = text.strip().upper()
    match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)?', text)
    if not match:
        match = re.search(r'(\d{1,2})\s*(AM|PM)', text)
        if match:
            hour = int(match.group(1))
            meridiem = match.group(2)
            minute = 0
        else:
            match = re.search(r'(\d{1,2}):(\d{2})', text)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                meridiem = None
            else:
                return None
    else:
        hour = int(match.group(1))
        minute = int(match.group(2))
        meridiem = match.group(3) if match.lastindex >= 3 else None
    if meridiem == "PM" and hour != 12: hour += 12
    elif meridiem == "AM" and hour == 12: hour = 0
    if hour > 23 or minute > 59: return None
    now = datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now: target += timedelta(days=1)
    return target

def format_duration(seconds):
    if seconds < 60: return f"{int(seconds)} second{'s' if seconds != 1 else ''}"
    elif seconds < 3600:
        mins = int(seconds / 60)
        secs = int(seconds % 60)
        parts = [f"{mins} minute{'s' if mins != 1 else ''}"]
        if secs > 0: parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        return " and ".join(parts)
    else:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        parts = [f"{hours} hour{'s' if hours != 1 else ''}"]
        if mins > 0: parts.append(f"{mins} minute{'s' if mins != 1 else ''}")
        return " and ".join(parts)

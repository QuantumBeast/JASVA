"""
JASVA Cognitive NLP Engine
─────────────────────────
Zero-dependency natural language processing pipeline that runs locally
before every LLM call, giving JASVA real language understanding.

Components:
  SlangNormalizer    → Expands Gen-Z abbreviations into clean English
  SentimentAnalyzer  → VADER-inspired lexicon-based valence scoring
  EntityExtractor    → Regex NER for time, paths, apps, URLs, names, numbers
  IntentClassifier   → TF-IDF + rule-based intent detection (15+ categories)
  CoreferenceResolver→ Pronoun-to-entity linking across conversation turns
  TFIDFVectorizer    → Reusable vectorizer for both intent and memory search
  NLPPipeline        → Orchestrator that runs all components and returns structured analysis
"""

import re
import math
from collections import Counter, defaultdict

# ──────────────────────────────────────────────────────────────
# Slang / Abbreviation Normalizer
# ──────────────────────────────────────────────────────────────
_SLANG_MAP = {
    "fr": "for real", "ngl": "not gonna lie", "tbh": "to be honest",
    "rn": "right now", "smh": "shaking my head", "imo": "in my opinion",
    "imho": "in my honest opinion", "idk": "I don't know", "idc": "I don't care",
    "idgaf": "I don't care at all", "lmk": "let me know", "lmao": "laughing",
    "lol": "laughing", "rofl": "laughing hard", "brb": "be right back",
    "gtg": "got to go", "ttyl": "talk to you later", "omg": "oh my god",
    "omfg": "oh my god", "wtf": "what the heck", "wth": "what the heck",
    "af": "as heck", "lowkey": "somewhat", "highkey": "definitely",
    "no cap": "no lie", "cap": "lie", "bussin": "really good",
    "slay": "amazing", "bet": "okay sure", "finna": "going to",
    "goat": "greatest of all time", "goated": "the greatest",
    "rizz": "charisma", "w": "win", "l": "loss",
    "mid": "mediocre", "sus": "suspicious", "salty": "bitter",
    "vibe": "feeling", "vibes": "feelings", "vibing": "relaxing",
    "ghosted": "ignored", "flex": "show off", "slaps": "is great",
    "hits different": "feels special", "deadass": "seriously",
    "sheesh": "wow", "yeet": "throw", "periodt": "period",
    "ong": "on god", "fam": "family", "bro": "brother",
    "bruh": "dude", "sis": "sister", "bestie": "best friend",
    "nah": "no", "yep": "yes", "yup": "yes", "ya": "yes",
    "gonna": "going to", "wanna": "want to", "gotta": "got to",
    "kinda": "kind of", "sorta": "sort of", "tryna": "trying to",
    "prolly": "probably", "tho": "though", "thru": "through",
    "cuz": "because", "cos": "because", "bc": "because",
    "pls": "please", "plz": "please", "thx": "thanks",
    "ty": "thank you", "tysm": "thank you so much", "np": "no problem",
    "yw": "you're welcome", "ofc": "of course", "obvi": "obviously",
    "nvm": "never mind", "jk": "just kidding", "ik": "I know",
    "ikr": "I know right", "wya": "where are you", "hmu": "hit me up",
    "dm": "direct message", "ftw": "for the win", "fwiw": "for what it's worth",
    "tldr": "too long didn't read", "smth": "something", "sth": "something",
    "rly": "really", "v": "very", "p": "pretty",
    "abt": "about", "w/": "with", "w/o": "without",
    "b4": "before", "2day": "today", "2moro": "tomorrow",
    "2nite": "tonight", "ur": "your", "u": "you",
    "r": "are", "y": "why", "k": "okay",
    "cba": "can't be bothered", "icl": "I can't lie",
    "istg": "I swear to god", "wdym": "what do you mean",
    "stfu": "shut up", "gtfo": "get out", "asap": "as soon as possible",
    "eta": "estimated time of arrival", "fyi": "for your information",
    "tbf": "to be fair", "iirc": "if I recall correctly",
    "afaik": "as far as I know", "afk": "away from keyboard",
}

def normalize_slang(text):
    """Expand slang/abbreviations into clean English for NLP processing.
    Returns (normalized_text, expansions_dict)."""
    words = text.split()
    expansions = {}
    result = []
    for word in words:
        clean = word.lower().strip(".,!?;:'\"()[]{}…")
        if clean in _SLANG_MAP:
            expansion = _SLANG_MAP[clean]
            expansions[clean] = expansion
            # Preserve punctuation that was attached
            suffix = word[len(clean):] if len(word) > len(clean) else ""
            result.append(expansion + suffix)
        else:
            result.append(word)
    return " ".join(result), expansions


# ──────────────────────────────────────────────────────────────
# Sentiment Analyzer (VADER-inspired, zero dependencies)
# ──────────────────────────────────────────────────────────────
_SENTIMENT_LEXICON = {
    # Strong positive
    "love": 0.9, "amazing": 0.85, "awesome": 0.85, "excellent": 0.85,
    "fantastic": 0.85, "wonderful": 0.85, "great": 0.8, "perfect": 0.9,
    "beautiful": 0.8, "brilliant": 0.85, "outstanding": 0.85,
    "incredible": 0.85, "superb": 0.85, "magnificent": 0.85,
    "happy": 0.8, "excited": 0.8, "thrilled": 0.85, "ecstatic": 0.9,
    "delighted": 0.85, "grateful": 0.8, "thankful": 0.8,
    "blessed": 0.75, "proud": 0.75, "accomplished": 0.7,
    # Moderate positive
    "good": 0.6, "nice": 0.55, "fine": 0.3, "okay": 0.15,
    "cool": 0.55, "fun": 0.65, "enjoy": 0.7, "like": 0.5,
    "helpful": 0.6, "useful": 0.55, "interesting": 0.55,
    "pleasant": 0.6, "comfortable": 0.5, "satisfied": 0.6,
    "relieved": 0.5, "glad": 0.6, "cheerful": 0.7,
    "optimistic": 0.65, "confident": 0.6, "motivated": 0.65,
    "inspired": 0.7, "energized": 0.65, "peaceful": 0.6,
    # Mild positive
    "thanks": 0.4, "thank": 0.4, "please": 0.2, "sure": 0.2,
    "yes": 0.15, "alright": 0.15, "agreed": 0.3,
    # Strong negative
    "hate": -0.9, "terrible": -0.85, "horrible": -0.85, "awful": -0.85,
    "disgusting": -0.9, "worst": -0.9, "dreadful": -0.85,
    "miserable": -0.85, "furious": -0.9, "outraged": -0.85,
    "devastated": -0.9, "heartbroken": -0.85, "depressed": -0.85,
    "suicidal": -0.95, "hopeless": -0.85, "worthless": -0.85,
    # Moderate negative
    "bad": -0.6, "sad": -0.65, "angry": -0.7, "annoyed": -0.6,
    "frustrated": -0.65, "disappointed": -0.65, "upset": -0.65,
    "worried": -0.55, "anxious": -0.6, "stressed": -0.65,
    "tired": -0.45, "exhausted": -0.6, "bored": -0.5,
    "confused": -0.4, "lost": -0.45, "stuck": -0.45,
    "lonely": -0.65, "scared": -0.6, "afraid": -0.6,
    "nervous": -0.5, "overwhelmed": -0.65, "struggling": -0.6,
    # Mild negative
    "meh": -0.3, "nah": -0.2, "no": -0.15, "not": -0.25,
    "don't": -0.2, "can't": -0.2, "won't": -0.2,
    "sucks": -0.7, "boring": -0.55, "ugly": -0.65,
    "stupid": -0.7, "dumb": -0.65, "useless": -0.7,
    "broken": -0.55, "failed": -0.6, "fail": -0.6,
}

_INTENSIFIERS = {
    "very": 1.3, "really": 1.3, "so": 1.25, "extremely": 1.5,
    "incredibly": 1.5, "absolutely": 1.4, "totally": 1.3,
    "completely": 1.35, "utterly": 1.4, "super": 1.3,
    "quite": 1.15, "pretty": 1.1, "rather": 1.1,
    "somewhat": 0.8, "slightly": 0.7, "barely": 0.6,
    "hardly": 0.5, "a bit": 0.8, "kinda": 0.8, "sorta": 0.8,
}

_NEGATORS = {"not", "no", "never", "neither", "nor", "hardly", "barely",
             "scarcely", "don't", "doesn't", "didn't", "won't", "wouldn't",
             "can't", "cannot", "couldn't", "shouldn't", "isn't", "aren't",
             "wasn't", "weren't", "haven't", "hasn't", "hadn't"}


def analyze_sentiment(text):
    """Compute sentiment valence on [-1.0, +1.0] scale.
    Returns dict with valence, magnitude, dominant_emotion, and word_scores."""
    words = re.findall(r"[\w']+", text.lower())
    scores = []
    word_scores = {}
    negation_window = 0

    for i, word in enumerate(words):
        if word in _NEGATORS:
            negation_window = 3  # next 3 words get flipped
            continue

        score = _SENTIMENT_LEXICON.get(word, 0.0)
        if score == 0.0:
            if negation_window > 0:
                negation_window -= 1
            continue

        # Check preceding word for intensifier
        if i > 0 and words[i - 1] in _INTENSIFIERS:
            score *= _INTENSIFIERS[words[i - 1]]

        # Apply negation
        if negation_window > 0:
            score *= -0.75
            negation_window -= 1

        # ALL CAPS amplification (check original text)
        original_words = text.split()
        if i < len(original_words) and original_words[i].isupper() and len(original_words[i]) > 1:
            score *= 1.3

        score = max(-1.0, min(1.0, score))
        scores.append(score)
        word_scores[word] = round(score, 3)

    if not scores:
        valence = 0.0
        magnitude = 0.0
    else:
        valence = sum(scores) / len(scores)
        magnitude = sum(abs(s) for s in scores) / len(scores)

    # Exclamation marks boost magnitude
    excl_count = text.count("!")
    if excl_count > 0:
        magnitude = min(1.0, magnitude * (1 + 0.1 * excl_count))

    # Question marks slightly reduce certainty
    if text.count("?") > 0:
        magnitude *= 0.9

    # Map to dominant emotion
    if valence > 0.5:
        dominant = "happy"
    elif valence > 0.2:
        dominant = "positive"
    elif valence > -0.2:
        dominant = "neutral"
    elif valence > -0.5:
        dominant = "negative"
    else:
        dominant = "distressed"

    # Detect specific emotions from keywords
    text_lower = text.lower()
    if any(w in text_lower for w in ("angry", "furious", "mad", "pissed", "rage")):
        dominant = "angry"
    elif any(w in text_lower for w in ("sad", "depressed", "crying", "heartbroken", "lonely")):
        dominant = "sad"
    elif any(w in text_lower for w in ("anxious", "worried", "nervous", "scared", "afraid")):
        dominant = "anxious"
    elif any(w in text_lower for w in ("excited", "thrilled", "pumped", "hyped", "ecstatic")):
        dominant = "excited"
    elif any(w in text_lower for w in ("tired", "exhausted", "sleepy", "drained", "burnt out")):
        dominant = "tired"
    elif any(w in text_lower for w in ("bored", "boring", "meh")):
        dominant = "bored"
    elif any(w in text_lower for w in ("grateful", "thankful", "blessed", "appreciate")):
        dominant = "grateful"

    return {
        "valence": round(valence, 3),
        "magnitude": round(magnitude, 3),
        "dominant_emotion": dominant,
        "word_scores": word_scores,
    }


# ──────────────────────────────────────────────────────────────
# Entity Extractor (Regex NER)
# ──────────────────────────────────────────────────────────────
_TIME_PATTERNS = [
    (r'\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)\b', "time"),
    (r'\b(\d{1,2}\s*(?:AM|PM|am|pm))\b', "time"),
    (r'\b(today|tomorrow|yesterday|tonight|this morning|this afternoon|this evening)\b', "relative_time"),
    (r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', "day"),
    (r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b', "date"),
    (r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', "date"),
    (r'\b(\d+)\s*(seconds?|minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?)\b', "duration"),
]

_APP_NAMES = {
    "notepad", "calculator", "paint", "chrome", "firefox", "edge",
    "spotify", "discord", "slack", "telegram", "whatsapp",
    "vscode", "code", "visual studio", "sublime", "atom",
    "word", "excel", "powerpoint", "outlook", "teams",
    "netflix", "youtube", "twitter", "instagram", "facebook",
    "steam", "epic games", "minecraft", "valorant", "fortnite",
    "explorer", "file explorer", "task manager", "cmd", "terminal",
    "powershell", "settings", "control panel", "photoshop",
    "premiere", "audacity", "obs", "vlc", "media player",
    "github", "postman", "docker", "blender", "unity", "unreal",
}

_URL_PATTERN = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|^`\[\]]+'
)
_FILE_PATH_PATTERN = re.compile(
    r'[A-Za-z]:\\[^\s<>"{}|^`\[\]:*?]+|~/[^\s<>"{}|^`\[\]]+|/[a-z][^\s<>"{}|^`\[\]]+'
)
_EMAIL_PATTERN = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_NUMBER_PATTERN = re.compile(r'\b\d+(?:\.\d+)?\b')


def extract_entities(text):
    """Extract named entities from text. Returns dict of entity_type -> list of values."""
    entities = defaultdict(list)

    # Time expressions
    for pattern, etype in _TIME_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            entities[etype].append(match.group(0).strip())

    # URLs
    for match in _URL_PATTERN.finditer(text):
        entities["url"].append(match.group(0))

    # File paths
    for match in _FILE_PATH_PATTERN.finditer(text):
        entities["file_path"].append(match.group(0))

    # Email addresses
    for match in _EMAIL_PATTERN.finditer(text):
        entities["email"].append(match.group(0))

    # Application names
    text_lower = text.lower()
    for app in _APP_NAMES:
        if re.search(rf'\b{re.escape(app)}\b', text_lower):
            entities["app"].append(app)

    # Numbers (excluding those already captured in time/duration)
    all_time_spans = set()
    for pattern, _ in _TIME_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            for i in range(match.start(), match.end()):
                all_time_spans.add(i)

    for match in _NUMBER_PATTERN.finditer(text):
        if not any(i in all_time_spans for i in range(match.start(), match.end())):
            entities["number"].append(match.group(0))

    return dict(entities)


# ──────────────────────────────────────────────────────────────
# Intent Classifier (Rule-based + TF-IDF)
# ──────────────────────────────────────────────────────────────
_INTENT_RULES = [
    # (pattern_list, intent, base_confidence)
    ([r'\b(hi|hello|hey|howdy|good\s*morning|good\s*afternoon|good\s*evening|sup|what\'s\s*up|yo)\b'],
     "greeting", 0.85),
    ([r'\b(bye|goodbye|see\s*ya|later|goodnight|good\s*night|gotta\s*go|ttyl)\b'],
     "farewell", 0.85),
    ([r'\b(thank|thanks|thx|ty|tysm|appreciate|grateful)\b'],
     "gratitude", 0.80),
    ([r'\b(sorry|apolog|my\s*bad|forgive)\b'],
     "apology", 0.80),
    # Commands
    ([r'\b(open|launch|start|run|execute|close|kill|stop|shut\s*down|restart|minimize|maximize)\b'],
     "command", 0.70),
    ([r'\b(set\s*(timer|alarm|reminder)|remind\s*me|schedule|create\s*(folder|file)|delete|remove|empty|clean)\b'],
     "command", 0.75),
    ([r'\b(volume|brightness|mute|unmute|screenshot|lock\s*pc|sleep|hibernate|shutdown|turn\s*(on|off))\b'],
     "system_control", 0.80),
    # Questions
    ([r'^(what|who|where|when|why|how|which|is|are|do|does|did|can|could|would|should|will)\b',
      r'\?\s*$'],
     "question", 0.70),
    # Search / research
    ([r'\b(search|google|look\s*up|find\s*out|research|wiki)\b'],
     "search", 0.75),
    # Media
    ([r'\b(play|pause|resume|next\s*track|previous\s*track|stop\s*music|spotify|youtube|netflix)\b'],
     "media", 0.75),
    # Memory operations
    ([r'\b(remember|memorize|don\'t\s*forget|keep\s*in\s*mind|what\s*do\s*you\s*(know|remember))\b'],
     "memory", 0.80),
    ([r'\b(forget|clear\s*memory|erase|delete\s*memory)\b'],
     "memory_delete", 0.80),
    # Emotional / venting
    ([r'\b(feel|feeling|felt|mood|emotion|stressed|anxious|depressed|sad|angry|upset|frustrated|lonely|scared|worried)\b'],
     "emotional", 0.65),
    ([r'\b(vent|rant|ugh|argh|fml|hate\s*my\s*life|can\'t\s*take\s*it)\b'],
     "emotional_vent", 0.80),
    # Opinion / discussion
    ([r'\b(think|opinion|believe|reckon|feel\s*like|seems?\s*like|do\s*you\s*think)\b'],
     "opinion", 0.55),
    # Creative requests
    ([r'\b(write|compose|create|generate|draft|make\s*a|come\s*up\s*with|brainstorm|imagine|story|poem|essay|code|script)\b'],
     "creative", 0.65),
    # Notes
    ([r'\b(note|notes|add\s*note|show\s*notes|list\s*notes|my\s*notes)\b'],
     "notes", 0.80),
    # Weather
    ([r'\b(weather|temperature|forecast|rain|sunny|cloudy|snow)\b'],
     "weather", 0.80),
    # Conversational / chitchat
    ([r'\b(bored|chat|talk|tell\s*me\s*(a\s*joke|something|about)|how\s*are\s*you|what\s*can\s*you\s*do)\b'],
     "chitchat", 0.65),
]


def classify_intent(text, normalized_text=None):
    """Classify user intent using rule-based pattern matching.
    Returns list of (intent, confidence) tuples sorted by confidence descending."""
    check_text = normalized_text or text
    check_lower = check_text.lower()
    scores = defaultdict(float)

    for patterns, intent, base_conf in _INTENT_RULES:
        for pattern in patterns:
            if re.search(pattern, check_lower, re.IGNORECASE):
                # Accumulate — multiple matches boost confidence
                scores[intent] = max(scores[intent], base_conf)
                break

    # Boost question intent if ends with ?
    if check_text.strip().endswith("?"):
        scores["question"] = max(scores.get("question", 0), 0.6)

    # If nothing matched, it's likely conversational
    if not scores:
        scores["conversational"] = 0.5

    # Sort by confidence
    results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return results


# ──────────────────────────────────────────────────────────────
# Coreference Resolution
# ──────────────────────────────────────────────────────────────
_PRONOUNS_SINGULAR = {"it", "its", "this", "that", "itself"}
_PRONOUNS_PERSON = {"he", "him", "his", "himself", "she", "her", "hers", "herself"}
_PRONOUNS_PLURAL = {"they", "them", "their", "theirs", "themselves", "those", "these"}
_REFERENTIAL = {"the same", "the one", "that thing", "that one", "it again",
                "do it again", "same thing", "the last one"}


class CoreferenceResolver:
    """Tracks entities across conversation turns and resolves pronouns."""

    def __init__(self):
        self._entity_stack = []  # Stack of (entity_text, entity_type, turn_index)
        self._turn_count = 0

    def update(self, text, entities, turn_index=None):
        """Register entities mentioned in the current turn."""
        if turn_index is not None:
            self._turn_count = turn_index
        else:
            self._turn_count += 1

        # Push recognized entities onto the stack
        for etype, values in entities.items():
            for val in values:
                self._entity_stack.append((val, etype, self._turn_count))

        # Also extract noun phrases as potential referents (simple heuristic)
        # Look for capitalized words that aren't at sentence starts
        words = text.split()
        for i, word in enumerate(words):
            clean = word.strip(".,!?;:'\"()[]{}…")
            if clean and clean[0].isupper() and i > 0 and len(clean) > 1:
                if clean.lower() not in _SLANG_MAP and clean.lower() not in {"i", "the", "a", "an"}:
                    self._entity_stack.append((clean, "noun", self._turn_count))

        # Keep stack bounded
        self._entity_stack = self._entity_stack[-30:]

    def resolve(self, text):
        """Find pronouns in text and attempt to resolve them.
        Returns dict of pronoun -> resolved_entity."""
        resolutions = {}
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))

        # Check for referential phrases first
        for phrase in _REFERENTIAL:
            if phrase in text_lower and self._entity_stack:
                last = self._entity_stack[-1]
                resolutions[phrase] = {"text": last[0], "type": last[1]}

        # Resolve singular pronouns -> most recent non-person entity
        if words & _PRONOUNS_SINGULAR:
            for entity, etype, _ in reversed(self._entity_stack):
                if etype not in ("noun",):
                    for pronoun in words & _PRONOUNS_SINGULAR:
                        resolutions[pronoun] = {"text": entity, "type": etype}
                    break

        # Resolve person pronouns -> most recent person/noun entity
        if words & _PRONOUNS_PERSON:
            for entity, etype, _ in reversed(self._entity_stack):
                if etype in ("noun", "name"):
                    for pronoun in words & _PRONOUNS_PERSON:
                        resolutions[pronoun] = {"text": entity, "type": etype}
                    break

        return resolutions


# ──────────────────────────────────────────────────────────────
# TF-IDF Vectorizer (reusable for intent + memory)
# ──────────────────────────────────────────────────────────────
_STOP_WORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "yourselves", "he", "him", "his",
    "himself", "she", "her", "hers", "herself", "it", "its", "itself",
    "they", "them", "their", "theirs", "themselves", "what", "which",
    "who", "whom", "this", "that", "these", "those", "am", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "having",
    "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if",
    "or", "because", "as", "until", "while", "of", "at", "by", "for",
    "with", "about", "against", "between", "through", "during", "before",
    "after", "above", "below", "to", "from", "up", "down", "in", "out",
    "on", "off", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "s", "t",
    "can", "will", "just", "don", "should", "now", "d", "ll", "m", "o",
    "re", "ve", "y", "ain", "aren", "couldn", "didn", "doesn", "hadn",
    "hasn", "haven", "isn", "ma", "mightn", "mustn", "needn", "shan",
    "shouldn", "wasn", "weren", "won", "wouldn",
}


def tokenize(text):
    """Tokenize text into lowercase word tokens, excluding stop words."""
    words = re.findall(r'\b[a-z]+\b', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


class TFIDFVectorizer:
    """Lightweight TF-IDF vectorizer for semantic similarity search."""

    def __init__(self):
        self._idf = {}
        self._vocab = set()
        self._doc_count = 0

    def fit(self, documents):
        """Build IDF from a corpus of documents (list of strings)."""
        self._doc_count = len(documents)
        df = Counter()
        for doc in documents:
            unique_terms = set(tokenize(doc))
            for term in unique_terms:
                df[term] += 1
            self._vocab.update(unique_terms)
        # Compute IDF with smoothing
        for term, count in df.items():
            self._idf[term] = math.log((1 + self._doc_count) / (1 + count)) + 1

    def transform(self, text):
        """Convert text to TF-IDF vector (sparse dict)."""
        tokens = tokenize(text)
        if not tokens:
            return {}
        tf = Counter(tokens)
        max_tf = max(tf.values()) if tf else 1
        vector = {}
        for term, count in tf.items():
            tf_val = 0.5 + 0.5 * (count / max_tf)  # Augmented TF
            idf_val = self._idf.get(term, math.log(1 + self._doc_count) + 1)
            vector[term] = tf_val * idf_val
        return vector

    @staticmethod
    def cosine_similarity(vec_a, vec_b):
        """Compute cosine similarity between two sparse vectors (dicts)."""
        if not vec_a or not vec_b:
            return 0.0
        common = set(vec_a.keys()) & set(vec_b.keys())
        if not common:
            return 0.0
        dot = sum(vec_a[k] * vec_b[k] for k in common)
        mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
        mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)


# ──────────────────────────────────────────────────────────────
# NLP Pipeline Orchestrator
# ──────────────────────────────────────────────────────────────
class NLPPipeline:
    """Orchestrates all NLP components into a single analyze() call."""

    def __init__(self):
        self.coref = CoreferenceResolver()
        self.vectorizer = TFIDFVectorizer()
        self._analysis_count = 0

    def analyze(self, text, history=None):
        """Run the full NLP pipeline on user text.

        Args:
            text: Raw user input string
            history: Optional list of {"role": str, "content": str} dicts

        Returns:
            dict with keys:
                original_text, normalized_text, slang_expansions,
                sentiment, entities, intents, coreferences,
                analysis_id
        """
        self._analysis_count += 1

        # 1. Normalize slang
        normalized, expansions = normalize_slang(text)

        # 2. Sentiment analysis (on normalized text for accuracy)
        sentiment = analyze_sentiment(normalized)

        # 3. Entity extraction (on original text to preserve casing/paths)
        entities = extract_entities(text)

        # 4. Intent classification (on normalized text)
        intents = classify_intent(text, normalized)

        # 5. Coreference resolution
        # First, update with entities from recent history
        if history:
            for i, msg in enumerate(history[-5:]):
                if msg.get("role") == "user":
                    hist_entities = extract_entities(msg.get("content", ""))
                    self.coref.update(msg["content"], hist_entities, turn_index=i)

        self.coref.update(text, entities)
        coreferences = self.coref.resolve(text)

        return {
            "original_text": text,
            "normalized_text": normalized,
            "slang_expansions": expansions,
            "sentiment": sentiment,
            "entities": entities,
            "intents": intents,
            "coreferences": coreferences,
            "analysis_id": self._analysis_count,
        }

    def format_for_prompt(self, analysis):
        """Format NLP analysis into a concise string for LLM prompt injection."""
        parts = []

        # Intent
        if analysis["intents"]:
            top_intents = [f"{intent}({conf:.0%})" for intent, conf in analysis["intents"][:3]]
            parts.append(f"Detected intents: {', '.join(top_intents)}")

        # Sentiment
        s = analysis["sentiment"]
        parts.append(f"User mood: {s['dominant_emotion']} (valence={s['valence']:+.2f}, intensity={s['magnitude']:.2f})")

        # Entities
        if analysis["entities"]:
            ent_strs = []
            for etype, values in analysis["entities"].items():
                ent_strs.append(f"{etype}: {', '.join(values[:3])}")
            parts.append(f"Entities: {'; '.join(ent_strs)}")

        # Coreferences
        if analysis["coreferences"]:
            coref_strs = [f"'{pronoun}' -> '{ref['text']}'" for pronoun, ref in analysis["coreferences"].items()]
            parts.append(f"References: {'; '.join(coref_strs)}")

        # Slang expansions
        if analysis["slang_expansions"]:
            parts.append(f"Slang decoded: {', '.join(f'{k}->{v}' for k, v in list(analysis['slang_expansions'].items())[:5])}")

        return "\n".join(parts)

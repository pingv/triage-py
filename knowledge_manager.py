"""
Knowledge Manager - Local pattern storage, caching, and retrieval
This is the AI's "memory" - it stores analyses and learned patterns locally.
"""

import json
import os
from datetime import datetime
from difflib import SequenceMatcher

import config


ANALYSES_FILE = os.path.join(config.KNOWLEDGE_DIR, "analyses.json")
PATTERNS_FILE = os.path.join(config.KNOWLEDGE_DIR, "patterns.json")


def _load_json(filepath):
    """Load a JSON file, return empty dict/list if missing."""
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return {}


def _save_json(filepath, data):
    """Save data to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# =========================================================================
# Analysis Storage - stores every triage result
# =========================================================================

def save_analysis(ticket_key, analysis_data):
    """
    Store a completed analysis for future reference.
    """
    analyses = _load_json(ANALYSES_FILE)
    if not isinstance(analyses, dict):
        analyses = {}

    analyses[ticket_key] = {
        "timestamp": datetime.now().isoformat(),
        "ticket_key": ticket_key,
        "summary": analysis_data.get("summary", ""),
        "description_snippet": analysis_data.get("description", "")[:200],
        "similar_tickets": analysis_data.get("similar_tickets", []),
        "ai_analysis": analysis_data.get("ai_analysis", ""),
        "confidence": analysis_data.get("confidence", "unknown"),
    }

    _save_json(ANALYSES_FILE, analyses)
    print(f"  💾 Analysis saved for {ticket_key}")


def find_previous_analysis(ticket_key):
    """Check if we already analyzed this exact ticket."""
    analyses = _load_json(ANALYSES_FILE)
    return analyses.get(ticket_key)


def find_similar_analyses(summary, threshold=0.6):
    """
    Search past analyses for similar issues (by summary text similarity).
    Returns matches above the similarity threshold.
    """
    analyses = _load_json(ANALYSES_FILE)
    if not analyses:
        return []

    matches = []
    for key, analysis in analyses.items():
        stored_summary = analysis.get("summary", "")
        similarity = SequenceMatcher(None, summary.lower(), stored_summary.lower()).ratio()
        if similarity >= threshold:
            matches.append({
                "ticket_key": key,
                "similarity": round(similarity, 2),
                "summary": stored_summary,
                "ai_analysis": analysis.get("ai_analysis", ""),
                "timestamp": analysis.get("timestamp", ""),
            })

    # Sort by similarity descending
    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return matches[:5]  # Return top 5


# =========================================================================
# Pattern Storage - extracted recurring patterns
# =========================================================================

def get_all_patterns():
    """Return all known patterns."""
    return _load_json(PATTERNS_FILE)


def add_pattern(pattern_data):
    """
    Add or update a pattern in the knowledge base.
    Patterns are keyed by a pattern_id.
    """
    patterns = _load_json(PATTERNS_FILE)
    if not isinstance(patterns, dict):
        patterns = {}

    pattern_id = pattern_data.get("pattern_id")
    if not pattern_id:
        # Auto-generate ID
        pattern_id = f"PAT-{len(patterns) + 1:04d}"
        pattern_data["pattern_id"] = pattern_id

    patterns[pattern_id] = {
        **pattern_data,
        "last_updated": datetime.now().isoformat(),
    }

    _save_json(PATTERNS_FILE, patterns)
    return pattern_id


def search_patterns(keywords):
    """
    Search patterns by keywords matching against symptoms and category.
    """
    patterns = _load_json(PATTERNS_FILE)
    if not patterns:
        return []

    matches = []
    keywords_lower = [k.lower() for k in keywords]

    for pid, pattern in patterns.items():
        score = 0
        searchable = " ".join([
            pattern.get("category", ""),
            " ".join(pattern.get("symptoms", [])),
            " ".join(pattern.get("root_causes", [])),
        ]).lower()

        for kw in keywords_lower:
            if kw in searchable:
                score += 1

        if score > 0:
            matches.append({**pattern, "_match_score": score})

    matches.sort(key=lambda x: x["_match_score"], reverse=True)
    return matches[:5]


# =========================================================================
# Statistics
# =========================================================================

def get_knowledge_stats():
    """Return stats about the knowledge base for display."""
    analyses = _load_json(ANALYSES_FILE)
    patterns = _load_json(PATTERNS_FILE)
    return {
        "total_analyses": len(analyses) if isinstance(analyses, dict) else 0,
        "total_patterns": len(patterns) if isinstance(patterns, dict) else 0,
    }

"""
JIRA Client - Fetch ticket details and search for similar historical issues
"""

import json
import os
import re
from datetime import datetime, timedelta

import requests

import config


def _headers():
    return {
        "Authorization": f"Bearer {config.JIRA_PAT}",
        "Content-Type": "application/json",
    }


def _cache_path(ticket_key):
    return os.path.join(config.CACHE_DIR, "tickets", f"{ticket_key}.json")


def _is_cache_fresh(path):
    if not os.path.exists(path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - mtime) < timedelta(hours=config.CACHE_TTL_HOURS)


def test_connection():
    """Test JIRA connectivity and return True/False."""
    try:
        url = f"{config.JIRA_BASE_URL}/rest/api/2/myself"
        resp = requests.get(url, headers=_headers(), verify=True, timeout=15)
        if resp.status_code == 200:
            user = resp.json()
            print(f"  ✓ JIRA: Connected as {user.get('displayName')}")
            return True
        else:
            print(f"  ✗ JIRA: HTTP {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ✗ JIRA: {e}")
        return False


def fetch_ticket(ticket_key):
    """
    Fetch full details for a single ticket.
    Uses local cache if available and fresh.
    """
    cache_file = _cache_path(ticket_key)

    # Check cache first
    if _is_cache_fresh(cache_file):
        print(f"  ⟳ Using cached data for {ticket_key}")
        with open(cache_file, "r") as f:
            return json.load(f)

    print(f"  ↓ Fetching {ticket_key} from JIRA...")
    try:
        url = f"{config.JIRA_BASE_URL}/rest/api/2/issue/{ticket_key}"
        params = {"fields": ",".join(config.JIRA_FIELDS)}
        resp = requests.get(url, headers=_headers(), params=params, verify=True, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            # Cache it
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)
            return data
        else:
            print(f"  ✗ Failed to fetch {ticket_key}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  ✗ Error fetching {ticket_key}: {e}")
        return None


def search_similar_tickets(summary, description="", exclude_key=None):
    """
    Search for historically similar tickets using text from the target ticket.
    Returns resolved/closed tickets that match keywords from the input.
    """
    # Extract meaningful keywords from summary and description
    keywords = _extract_keywords(summary, description)
    if not keywords:
        print("  ⚠ No meaningful keywords extracted for similarity search")
        return []

    # Build JQL: search resolved tickets across our projects with matching text
    projects_str = ", ".join(config.JIRA_PROJECTS)
    keyword_str = " ".join(keywords[:8])  # Limit to avoid JQL length issues

    jql = (
        f'project in ({projects_str}) '
        f'AND status in (Closed, Done, Completed, Resolved) '
        f'AND text ~ "{keyword_str}" '
        f'ORDER BY updated DESC'
    )

    print(f"  🔍 Searching for similar resolved tickets...")
    print(f"     Keywords: {keyword_str}")

    try:
        url = f"{config.JIRA_BASE_URL}/rest/api/2/search"
        payload = {
            "jql": jql,
            "fields": config.JIRA_FIELDS,
            "maxResults": config.JIRA_MAX_SIMILAR_RESULTS,
        }
        resp = requests.post(url, headers=_headers(), json=payload, verify=True, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            issues = data.get("issues", [])

            # Filter out the ticket we're analyzing
            if exclude_key:
                issues = [i for i in issues if i["key"] != exclude_key]

            print(f"  ✓ Found {len(issues)} similar resolved tickets")
            return issues
        else:
            print(f"  ✗ Similar ticket search failed: HTTP {resp.status_code}")
            # Fallback: try a simpler query with fewer keywords
            return _fallback_search(keywords[:3], projects_str, exclude_key)
    except Exception as e:
        print(f"  ✗ Error searching similar tickets: {e}")
        return []


def _fallback_search(keywords, projects_str, exclude_key=None):
    """Simpler search if the full-text search fails."""
    keyword_str = " ".join(keywords)
    jql = (
        f'project in ({projects_str}) '
        f'AND status in (Closed, Done, Completed, Resolved) '
        f'AND summary ~ "{keyword_str}" '
        f'ORDER BY updated DESC'
    )
    print(f"  🔍 Fallback search with: {keyword_str}")
    try:
        url = f"{config.JIRA_BASE_URL}/rest/api/2/search"
        payload = {"jql": jql, "fields": config.JIRA_FIELDS, "maxResults": 10}
        resp = requests.post(url, headers=_headers(), json=payload, verify=True, timeout=30)
        if resp.status_code == 200:
            issues = resp.json().get("issues", [])
            if exclude_key:
                issues = [i for i in issues if i["key"] != exclude_key]
            print(f"  ✓ Fallback found {len(issues)} tickets")
            return issues
        return []
    except:
        return []


def _extract_keywords(summary, description=""):
    """
    Extract meaningful keywords from ticket text.
    Removes common filler words to improve search quality.
    """
    stop_words = {
        "the", "is", "at", "which", "on", "a", "an", "and", "or", "but",
        "in", "with", "to", "for", "of", "not", "no", "can", "had", "has",
        "have", "was", "were", "been", "being", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "this", "that",
        "these", "those", "am", "are", "it", "its", "from", "by", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further",
        "then", "once", "here", "there", "when", "where", "why", "how",
        "all", "both", "each", "few", "more", "most", "other", "some",
        "such", "than", "too", "very", "just", "because", "about",
        "issue", "error", "problem", "please", "need", "help", "ticket",
        "client", "user", "reported", "report", "see", "also", "using",
    }

    text = f"{summary} {description or ''}"
    # Remove special characters, keep alphanumeric and hyphens (for ticket keys)
    words = re.findall(r'[a-zA-Z0-9][\w-]*', text.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique


def extract_ticket_summary(issue_data):
    """
    Extract a clean summary dict from raw JIRA issue data.
    Used for building context for the AI prompt.
    """
    fields = issue_data.get("fields", {})

    # Extract comments
    comments = []
    comment_data = fields.get("comment", {})
    if isinstance(comment_data, dict):
        for c in comment_data.get("comments", []):
            comments.append({
                "author": c.get("author", {}).get("displayName", "Unknown"),
                "created": c.get("created", ""),
                "body": c.get("body", "")[:500],  # Truncate long comments
            })

    # Extract linked issues
    links = []
    for link in fields.get("issuelinks", []):
        if "outwardIssue" in link:
            links.append({
                "type": link.get("type", {}).get("outward", "relates to"),
                "key": link["outwardIssue"]["key"],
                "summary": link["outwardIssue"]["fields"].get("summary", ""),
            })
        if "inwardIssue" in link:
            links.append({
                "type": link.get("type", {}).get("inward", "relates to"),
                "key": link["inwardIssue"]["key"],
                "summary": link["inwardIssue"]["fields"].get("summary", ""),
            })

    return {
        "key": issue_data.get("key"),
        "summary": fields.get("summary", ""),
        "description": fields.get("description", "") or "",
        "status": fields.get("status", {}).get("name", ""),
        "resolution": (fields.get("resolution") or {}).get("name", "Unresolved"),
        "priority": (fields.get("priority") or {}).get("name", ""),
        "project": fields.get("project", {}).get("key", ""),
        "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
        "reporter": (fields.get("reporter") or {}).get("displayName", "Unknown"),
        "created": fields.get("created", ""),
        "updated": fields.get("updated", ""),
        "resolved": fields.get("resolutiondate", ""),
        "labels": fields.get("labels", []),
        "components": [c.get("name") for c in fields.get("components", [])],
        "fix_versions": [v.get("name") for v in fields.get("fixVersions", [])],
        "comments": comments,
        "linked_issues": links,
    }

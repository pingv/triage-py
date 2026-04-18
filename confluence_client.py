"""
Confluence Client - Search and fetch relevant documentation
"""

import json
import os
import re
from datetime import datetime, timedelta

import requests

import config


def _headers():
    return {
        "Authorization": f"Bearer {config.CONFLUENCE_PAT}",
        "Content-Type": "application/json",
    }


def _cache_path(page_id):
    return os.path.join(config.CACHE_DIR, "confluence", f"{page_id}.json")


def _is_cache_fresh(path):
    if not os.path.exists(path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return (datetime.now() - mtime) < timedelta(hours=config.CACHE_TTL_HOURS)


def test_connection():
    """Test Confluence connectivity."""
    try:
        url = f"{config.CONFLUENCE_BASE_URL}/rest/api/user/current"
        resp = requests.get(url, headers=_headers(), verify=True, timeout=15)
        if resp.status_code == 200:
            user = resp.json()
            print(f"  ✓ Confluence: Connected as {user.get('displayName', user.get('username', 'OK'))}")
            return True
        else:
            print(f"  ⚠ Confluence: HTTP {resp.status_code} (will skip Confluence data)")
            return False
    except Exception as e:
        print(f"  ⚠ Confluence: {e} (will skip Confluence data)")
        return False


def search_pages(summary, description=""):
    """
    Search Confluence for pages related to the issue's TOPIC and SYMPTOMS.
    Does NOT search for the ticket key - searches for the actual problem content.

    Three sources of Confluence content:
    1. Core runbook pages (from confluence_docs.json, category=core_runbook) — ALWAYS loaded
    2. Category-matched pages (from confluence_docs.json) — loaded based on ticket keywords
    3. Dynamic search results — CQL search using ticket symptoms/topic
    """
    all_pages = []
    seen_ids = set()

    # Load the external docs registry
    docs_registry = _load_docs_registry()
    domain_knowledge = _load_domain_knowledge()

    # --- Part A: Always fetch core runbook pages ---
    core_pages = [p for p in docs_registry if p.get("category") == "core_runbook"]
    if core_pages:
        print(f"  📚 Fetching {len(core_pages)} core runbook pages...")
        for doc in core_pages:
            page_id = doc.get("page_id", "")
            if page_id and page_id != "REPLACE_WITH_PAGE_ID":
                page = fetch_page(page_id)
                if page:
                    page["_source"] = "core_knowledge"
                    page["_registry_notes"] = doc.get("notes", "")
                    all_pages.append(page)
                    seen_ids.add(page.get("id"))
        if all_pages:
            print(f"  ✓ Loaded {len(all_pages)} core pages")

    # --- Part B: Fetch category-matched pages based on ticket content ---
    matched_categories = _match_categories(summary, description, domain_knowledge)
    if matched_categories:
        print(f"  📂 Matched categories: {', '.join(matched_categories)}")
        category_docs = [
            p for p in docs_registry
            if p.get("category") in matched_categories
            and p.get("category") != "core_runbook"
        ]
        for doc in category_docs:
            page_id = doc.get("page_id", "")
            if page_id and page_id != "REPLACE_WITH_PAGE_ID" and page_id not in seen_ids:
                page = fetch_page(page_id)
                if page:
                    page["_source"] = "category_match"
                    page["_matched_category"] = doc.get("category", "")
                    all_pages.append(page)
                    seen_ids.add(page.get("id"))

    # --- Part C: Dynamic CQL search by topic/symptoms ---
    search_terms = _extract_search_terms(summary, description, domain_knowledge)

    if search_terms:
        searches_done = 0
        for terms in search_terms:
            if searches_done >= 3:
                break
            pages = _run_cql_search(terms)
            for page in pages:
                if page.get("id") not in seen_ids:
                    page["_source"] = "topic_search"
                    all_pages.append(page)
                    seen_ids.add(page.get("id"))
            searches_done += 1

    print(f"  ✓ Total Confluence pages gathered: {len(all_pages)}")
    return all_pages


def _load_docs_registry():
    """Load the confluence_docs.json registry file."""
    docs_file = os.path.join(config.KNOWLEDGE_DIR, "confluence_docs.json")
    if os.path.exists(docs_file):
        try:
            with open(docs_file, "r") as f:
                data = json.load(f)
            return data.get("pages", [])
        except Exception as e:
            print(f"  ⚠ Error reading confluence_docs.json: {e}")
    return []


def _load_domain_knowledge():
    """Load the domain_knowledge.json file."""
    dk_file = os.path.join(config.KNOWLEDGE_DIR, "domain_knowledge.json")
    if os.path.exists(dk_file):
        try:
            with open(dk_file, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"  ⚠ Error reading domain_knowledge.json: {e}")
    return {}


def _match_categories(summary, description, domain_knowledge):
    """
    Determine which Confluence doc categories are relevant based on ticket content.
    Uses category_keywords from domain_knowledge.json.
    """
    category_keywords = domain_knowledge.get("category_keywords", {})
    if not category_keywords or "_description" in category_keywords and len(category_keywords) <= 1:
        return ["general"]

    text = f"{summary} {description or ''}".lower()

    # Expand text using synonym mappings
    synonyms = domain_knowledge.get("keyword_synonyms", {}).get("mappings", {})
    expanded_text = text
    for canonical, variants in synonyms.items():
        for variant in variants:
            if variant.lower() in text:
                expanded_text += f" {canonical.lower()}"

    matched = []
    for category, keywords in category_keywords.items():
        if category.startswith("_"):
            continue
        for kw in keywords:
            if kw.lower() in expanded_text:
                matched.append(category)
                break  # One match per category is enough

    return matched if matched else ["general"]


def _extract_search_terms(summary, description="", domain_knowledge=None):
    """
    Extract multiple search term combinations from ticket content.
    Uses synonym mappings from domain_knowledge.json to expand search coverage.
    Returns a list of search strings to try, from most specific to broader.
    """
    stop_words = {
        "the", "is", "at", "which", "on", "a", "an", "and", "or", "but",
        "in", "with", "to", "for", "of", "not", "no", "can", "had", "has",
        "have", "was", "were", "been", "do", "does", "did", "will", "would",
        "this", "that", "these", "those", "it", "its", "from", "by", "as",
        "are", "am", "be", "being", "there", "here", "when", "where", "how",
        "all", "each", "more", "most", "some", "such", "than", "too", "very",
        "just", "about", "issue", "error", "problem", "please", "need",
        "help", "ticket", "client", "user", "reported", "report", "see",
        "also", "using", "getting", "showing", "display", "displays",
    }

    # Combine summary and first part of description
    text = f"{summary} {(description or '')[:300]}"
    words = re.findall(r'[a-zA-Z0-9][\w-]*', text.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]

    # Deduplicate preserving order
    seen = set()
    unique = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            unique.append(w)

    # Expand with synonyms from domain knowledge
    synonym_terms = []
    if domain_knowledge:
        synonyms = domain_knowledge.get("keyword_synonyms", {}).get("mappings", {})
        text_lower = text.lower()
        for canonical, variants in synonyms.items():
            # If any variant appears in the text, add the canonical term
            for variant in variants:
                if variant.lower() in text_lower and canonical.lower() not in seen:
                    synonym_terms.append(canonical.lower())
                    break
            # If the canonical appears in the text, add key variants
            if canonical.lower() in text_lower:
                for variant in variants[:2]:  # Add first 2 variants
                    v_lower = variant.lower()
                    if v_lower not in seen and len(v_lower) > 2:
                        synonym_terms.append(v_lower)

    searches = []

    # Search 1: Most specific - first 4-5 meaningful keywords
    if len(unique) >= 3:
        searches.append(" ".join(unique[:5]))

    # Search 2: Broader - different keyword combination
    if len(unique) >= 6:
        searches.append(" ".join(unique[2:7]))

    # Search 3: Synonym-expanded search
    if synonym_terms:
        combined = list(unique[:3]) + synonym_terms[:3]
        searches.append(" ".join(combined))

    # Search 4: Domain-specific terms (if present)
    domain_terms = [w for w in unique if w in {
        "overtime", "payroll", "schedule", "timeoff", "punch", "accrual",
        "configuration", "calculation", "policy", "threshold", "rule",
        "integration", "sync", "export", "import", "batch", "holiday",
        "shift", "rotation", "approval", "workflow", "attestation",
    }]
    if domain_terms:
        searches.append(" ".join(domain_terms[:4]))

    # Fallback: just summary keywords
    if not searches and unique:
        searches.append(" ".join(unique[:4]))

    return searches


def _run_cql_search(search_text):
    """Run a single CQL search and return page summaries."""
    # Build CQL - search in configured spaces
    spaces_cql = " or ".join([f'space="{s}"' for s in config.CONFLUENCE_SPACES])
    cql = f'({spaces_cql}) and text ~ "{search_text}" order by lastmodified desc'

    print(f"  🔍 Searching Confluence for: {search_text}")

    try:
        url = f"{config.CONFLUENCE_BASE_URL}/rest/api/content/search"
        params = {
            "cql": cql,
            "limit": config.CONFLUENCE_MAX_RESULTS,
            "expand": "body.storage,version,space",
        }
        resp = requests.get(url, headers=_headers(), params=params, verify=True, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            print(f"     Found {len(results)} pages")
            return [_extract_page_summary(r) for r in results]
        else:
            print(f"  ⚠ Confluence search returned HTTP {resp.status_code}")
            return []
    except Exception as e:
        print(f"  ⚠ Confluence search error: {e}")
        return []


def fetch_page(page_id):
    """Fetch a specific Confluence page by ID."""
    cache_file = _cache_path(str(page_id))

    if _is_cache_fresh(cache_file):
        with open(cache_file, "r") as f:
            return json.load(f)

    try:
        url = f"{config.CONFLUENCE_BASE_URL}/rest/api/content/{page_id}"
        params = {"expand": "body.storage,version,space"}
        resp = requests.get(url, headers=_headers(), params=params, verify=True, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            summary = _extract_page_summary(data)
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump(summary, f, indent=2)
            return summary
        return None
    except:
        return None


def _extract_page_summary(page_data):
    """Extract a clean summary from a Confluence page."""
    body_html = (
        page_data.get("body", {}).get("storage", {}).get("value", "")
    )
    # Strip HTML tags for a text-only version
    body_text = _strip_html(body_html)

    return {
        "id": page_data.get("id"),
        "title": page_data.get("title", ""),
        "space": page_data.get("space", {}).get("key", ""),
        "url": f"{config.CONFLUENCE_BASE_URL}{page_data.get('_links', {}).get('webui', '')}",
        "last_updated": page_data.get("version", {}).get("when", ""),
        "body_text": body_text[:2000],  # Truncate to keep prompt manageable
    }


def _strip_html(html_text):
    """Remove HTML tags and clean up whitespace."""
    if not html_text:
        return ""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

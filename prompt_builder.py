"""
Prompt Builder - Assembles gathered context into a structured AI prompt
This is the brain of the toolkit - it constructs the prompt that drives analysis quality.
"""

import json


def build_triage_prompt(
    ticket_summary,
    similar_tickets=None,
    confluence_pages=None,
    bitbucket_prs=None,
    bitbucket_commits=None,
    prior_analyses=None,
    known_patterns=None,
    domain_knowledge=None,
):
    """
    Build a comprehensive triage prompt from all gathered context.
    Returns the full prompt string ready for the AI.
    """
    sections = []

    # === System Context ===
    sections.append(_build_system_context())

    # === Domain Knowledge (synonyms, routing rules, false patterns) ===
    if domain_knowledge:
        sections.append(_build_domain_knowledge_section(domain_knowledge))

    # === Target Ticket ===
    sections.append(_build_ticket_section(ticket_summary))

    # === Prior Knowledge (if we've seen something similar) ===
    if prior_analyses:
        sections.append(_build_prior_analyses_section(prior_analyses))

    # === Known Patterns ===
    if known_patterns:
        sections.append(_build_patterns_section(known_patterns))

    # === Similar Historical Tickets ===
    if similar_tickets:
        sections.append(_build_similar_tickets_section(similar_tickets))

    # === Confluence Documentation ===
    if confluence_pages:
        sections.append(_build_confluence_section(confluence_pages))

    # === Bitbucket PRs and Commits ===
    if bitbucket_prs or bitbucket_commits:
        sections.append(_build_code_section(bitbucket_prs, bitbucket_commits))

    # === Instructions ===
    sections.append(_build_instructions())

    return "\n\n".join(sections)


def _build_system_context():
    return """=== ROLE ===
You are a senior ADP Workforce Now engineer specializing in Time & Attendance.
You are triaging a production support issue. Your goal is to:
1. Analyze the reported issue
2. Match it against historical patterns
3. Provide actionable diagnosis and resolution steps
4. Rate your confidence in the analysis

You have deep knowledge of:
- Pay policy configurations and overtime calculations
- Schedule management and time-off policies
- Time entry processing and validation
- Integration between scheduling, time, and payroll modules"""


def _build_domain_knowledge_section(dk):
    """Build a section with domain knowledge for the AI."""
    lines = ["=== DOMAIN KNOWLEDGE ===", ""]

    # Synonym awareness
    synonyms = dk.get("keyword_synonyms", {}).get("mappings", {})
    if synonyms:
        lines.append("TERMINOLOGY MAPPINGS (same concept, different words):")
        for canonical, variants in list(synonyms.items())[:10]:
            lines.append(f"  {canonical} = {', '.join(variants[:3])}")
        lines.append("")

    # Project routing
    routing = dk.get("project_routing", {})
    if routing:
        lines.append("PROJECT ROUTING (which project handles what):")
        for project, info in routing.items():
            if project.startswith("_"):
                continue
            desc = info.get("description", "")
            issues = ", ".join(info.get("typical_issues", [])[:3])
            lines.append(f"  {project}: {desc}")
            if issues:
                lines.append(f"    Handles: {issues}")
        lines.append("")

    # False patterns - critical for avoiding wrong matches
    false_patterns = dk.get("false_patterns", {}).get("examples", [])
    if false_patterns:
        lines.append("⚠ FALSE PATTERN WARNINGS (look similar but different root causes):")
        for fp in false_patterns:
            lines.append(f"  Symptom: {fp.get('symptom', '')}")
            lines.append(f"  Looks like: {fp.get('looks_like', '')}")
            lines.append(f"  But could actually be:")
            for alt in fp.get("but_actually_could_be", []):
                lines.append(f"    - {alt}")
            lines.append("")

    # Environment notes
    env_notes = dk.get("environment_notes", {}).get("notes", [])
    if env_notes:
        lines.append("ENVIRONMENT NOTES:")
        for note in env_notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)


def _build_ticket_section(ticket):
    lines = [
        "=== NEW TICKET TO TRIAGE ===",
        f"Key: {ticket.get('key', 'N/A')}",
        f"Project: {ticket.get('project', 'N/A')}",
        f"Summary: {ticket.get('summary', 'N/A')}",
        f"Status: {ticket.get('status', 'N/A')}",
        f"Priority: {ticket.get('priority', 'N/A')}",
        f"Assignee: {ticket.get('assignee', 'Unassigned')}",
        f"Reporter: {ticket.get('reporter', 'Unknown')}",
        f"Created: {ticket.get('created', 'N/A')}",
        f"Labels: {', '.join(ticket.get('labels', [])) or 'None'}",
        f"Components: {', '.join(ticket.get('components', [])) or 'None'}",
        "",
        "Description:",
        ticket.get("description", "(No description provided)"),
    ]

    # Add comments if present
    comments = ticket.get("comments", [])
    if comments:
        lines.append("")
        lines.append(f"Comments ({len(comments)} total):")
        for i, c in enumerate(comments[:5], 1):  # Limit to 5 most relevant
            lines.append(f"  [{i}] {c.get('author', 'Unknown')} ({c.get('created', '')}):")
            lines.append(f"      {c.get('body', '')}")

    # Add linked issues
    links = ticket.get("linked_issues", [])
    if links:
        lines.append("")
        lines.append("Linked Issues:")
        for link in links:
            lines.append(f"  - {link.get('type', 'relates to')} {link.get('key', '')}: {link.get('summary', '')}")

    return "\n".join(lines)


def _build_prior_analyses_section(prior_analyses):
    lines = [
        "=== PRIOR ANALYSES FROM KNOWLEDGE BASE ===",
        "(These are analyses from similar tickets we've seen before)",
        "",
    ]
    for pa in prior_analyses[:3]:
        lines.append(f"Ticket: {pa.get('ticket_key')} (Similarity: {pa.get('similarity', 'N/A')})")
        lines.append(f"Summary: {pa.get('summary', '')}")
        lines.append(f"Previous Analysis: {pa.get('ai_analysis', '')[:500]}")
        lines.append("---")
    return "\n".join(lines)


def _build_patterns_section(patterns):
    lines = [
        "=== KNOWN PATTERNS ===",
        "(Recurring issue patterns identified from historical data)",
        "",
    ]
    for p in patterns[:3]:
        lines.append(f"Pattern: {p.get('pattern_id', 'N/A')} - {p.get('category', 'N/A')}")
        lines.append(f"Symptoms: {', '.join(p.get('symptoms', []))}")
        lines.append(f"Known Root Causes: {', '.join(p.get('root_causes', []))}")
        lines.append(f"Resolution Steps: {', '.join(p.get('resolution_steps', []))}")
        lines.append(f"Times Seen: {p.get('times_seen', 'N/A')}")
        lines.append("---")
    return "\n".join(lines)


def _build_similar_tickets_section(similar_tickets):
    lines = [
        f"=== SIMILAR HISTORICAL TICKETS ({len(similar_tickets)} found) ===",
        "",
    ]
    for i, issue in enumerate(similar_tickets[:8], 1):  # Limit to 8
        fields = issue.get("fields", {})
        lines.append(f"[{i}] {issue.get('key', 'N/A')}: {fields.get('summary', 'N/A')}")
        lines.append(f"    Status: {fields.get('status', {}).get('name', 'N/A')}")
        lines.append(f"    Resolution: {(fields.get('resolution') or {}).get('name', 'N/A')}")

        # Include resolution comments (last 2 comments often have the fix)
        comments = fields.get("comment", {})
        if isinstance(comments, dict):
            comment_list = comments.get("comments", [])
            if comment_list:
                last_comments = comment_list[-2:]  # Last 2 comments
                for c in last_comments:
                    body = c.get("body", "")[:300]
                    lines.append(f"    Comment by {c.get('author', {}).get('displayName', '?')}: {body}")

        lines.append("")
    return "\n".join(lines)


def _build_confluence_section(pages):
    core_pages = [p for p in pages if p.get("_source") == "core_knowledge"]
    search_pages = [p for p in pages if p.get("_source") != "core_knowledge"]

    lines = [
        f"=== RELEVANT CONFLUENCE DOCUMENTATION ({len(pages)} pages) ===",
        "",
    ]

    if core_pages:
        lines.append("--- Core L1/L2 Knowledge Base ---")
        for page in core_pages:
            lines.append(f"Page: {page.get('title', 'N/A')}")
            lines.append(f"Space: {page.get('space', 'N/A')}")
            lines.append(f"URL: {page.get('url', 'N/A')}")
            lines.append(f"Content: {page.get('body_text', '')[:1500]}")
            lines.append("---")
        lines.append("")

    if search_pages:
        lines.append("--- Topic-Matched Documentation ---")
        for page in search_pages[:5]:
            lines.append(f"Page: {page.get('title', 'N/A')}")
            lines.append(f"Space: {page.get('space', 'N/A')}")
            lines.append(f"URL: {page.get('url', 'N/A')}")
            lines.append(f"Content: {page.get('body_text', '')[:800]}")
            lines.append("---")

    return "\n".join(lines)


def _build_code_section(prs, commits):
    lines = [
        "=== CODE CHANGES FROM SIMILAR RESOLVED TICKETS ===",
        "(These PRs and commits fixed similar issues in the past)",
        "",
    ]

    if prs:
        lines.append(f"Pull Requests ({len(prs)}):")
        for pr in prs[:5]:
            lines.append(f"  PR #{pr.get('id', '?')} [{pr.get('state', '?')}] - {pr.get('title', 'N/A')}")
            lines.append(f"    Repo: {pr.get('repo', 'N/A')} | Branch: {pr.get('source_branch', 'N/A')} → {pr.get('target_branch', 'N/A')}")
            lines.append(f"    Author: {pr.get('author', 'N/A')}")
            if pr.get("description"):
                lines.append(f"    Description: {pr['description'][:200]}")
            lines.append("")

    if commits:
        lines.append(f"Commits ({len(commits)}):")
        for c in commits[:5]:
            lines.append(f"  {c.get('id', '?')} - {c.get('message', 'N/A')}")
            lines.append(f"    Repo: {c.get('repo', 'N/A')} | Author: {c.get('author', 'N/A')}")

    return "\n".join(lines)


def _build_instructions():
    return """=== YOUR TASK ===
Analyze the new ticket above using all available context. Provide your response in this format:

## TRIAGE ANALYSIS FOR {ticket_key}

### 1. Issue Classification
- Category: (e.g., Pay Calculation, Schedule Config, Time Entry, Integration, etc.)
- Severity Assessment: (Critical / High / Medium / Low)
- Affected Module: (e.g., TIMPOLPAY - Pay Policy, TIMSCHED - Scheduling, etc.)

### 2. Root Cause Hypothesis
Based on the historical patterns and similar tickets, what is the most likely root cause?
Explain your reasoning.

### 3. Historical Pattern Match
- Which historical tickets does this most closely resemble?
- What was the resolution for those tickets?
- Confidence in pattern match: (High / Medium / Low)

### 4. Recommended Troubleshooting Steps
Provide numbered steps an engineer should follow to diagnose and resolve this issue.
Be specific - reference actual configuration screens, code paths, or settings.

### 5. Relevant Code Areas
Based on the PRs and commits, which code files or modules should the engineer examine?

### 6. Relevant Documentation
Which Confluence pages should the engineer review?

### 7. Confidence Rating
- Overall Confidence: (High / Medium / Low)
- Reasoning: Why this level of confidence?

### 8. Pattern Extraction
If this represents a new recurring pattern, describe it:
- Pattern Name:
- Symptoms:
- Root Cause:
- Resolution Steps:
(Write "N/A - matches existing pattern" if it matches a known one)"""

"""
Bitbucket Client - Search for related PRs and code changes
"""

import json
import os
import re
from datetime import datetime, timedelta

import requests

import config


def _headers():
    return {
        "Authorization": f"Bearer {config.BITBUCKET_PAT}",
        "Content-Type": "application/json",
    }


def test_connection():
    """Test Bitbucket connectivity."""
    try:
        # Bitbucket Server REST API - get current user
        url = f"{config.BITBUCKET_BASE_URL}/rest/api/1.0/users"
        params = {"limit": 1}
        resp = requests.get(url, headers=_headers(), params=params, verify=True, timeout=15)
        if resp.status_code == 200:
            print(f"  ✓ Bitbucket: Connected")
            return True
        else:
            print(f"  ⚠ Bitbucket: HTTP {resp.status_code} (will skip Bitbucket data)")
            return False
    except Exception as e:
        print(f"  ⚠ Bitbucket: {e} (will skip Bitbucket data)")
        return False


def search_prs_by_ticket(ticket_key):
    """
    Search for Pull Requests that reference a ticket key.
    Bitbucket Server doesn't have a great global search, so we look for
    PRs with the ticket key in the title or description across repos.
    """
    print(f"  🔍 Searching Bitbucket PRs for: {ticket_key}")

    all_prs = []

    try:
        repos = _get_repos()
        for repo_slug in repos[:10]:  # Limit to avoid timeout
            prs = _search_repo_prs(repo_slug, ticket_key)
            all_prs.extend(prs)

        print(f"  ✓ Found {len(all_prs)} related PRs")
        return all_prs
    except Exception as e:
        print(f"  ⚠ Bitbucket PR search error: {e}")
        return []


def search_commits_by_ticket(ticket_key):
    """
    Search for commits that reference a ticket key in the commit message.
    """
    print(f"  🔍 Searching Bitbucket commits for: {ticket_key}")

    all_commits = []

    try:
        repos = _get_repos()
        for repo_slug in repos[:10]:
            commits = _search_repo_commits(repo_slug, ticket_key)
            all_commits.extend(commits)

        print(f"  ✓ Found {len(all_commits)} related commits")
        return all_commits
    except Exception as e:
        print(f"  ⚠ Bitbucket commit search error: {e}")
        return []


def get_pr_details(project_key, repo_slug, pr_id):
    """Fetch detailed PR information including diff stats."""
    try:
        url = (
            f"{config.BITBUCKET_BASE_URL}/rest/api/1.0/projects/{project_key}"
            f"/repos/{repo_slug}/pull-requests/{pr_id}"
        )
        resp = requests.get(url, headers=_headers(), verify=True, timeout=15)
        if resp.status_code == 200:
            pr = resp.json()
            return _extract_pr_summary(pr, repo_slug)
        return None
    except:
        return None


def _get_repos():
    """Get list of repos in the configured project."""
    if config.BITBUCKET_REPOS:
        return config.BITBUCKET_REPOS

    try:
        url = (
            f"{config.BITBUCKET_BASE_URL}/rest/api/1.0/projects/"
            f"{config.BITBUCKET_PROJECT}/repos"
        )
        params = {"limit": 50}
        resp = requests.get(url, headers=_headers(), params=params, verify=True, timeout=15)
        if resp.status_code == 200:
            repos = resp.json().get("values", [])
            return [r["slug"] for r in repos]
        return []
    except:
        return []


def _search_repo_prs(repo_slug, search_text):
    """Search PRs in a specific repo."""
    try:
        url = (
            f"{config.BITBUCKET_BASE_URL}/rest/api/1.0/projects/"
            f"{config.BITBUCKET_PROJECT}/repos/{repo_slug}/pull-requests"
        )
        # Search in all states (OPEN, MERGED, DECLINED)
        params = {
            "state": "ALL",
            "limit": 10,
            "order": "NEWEST",
        }
        resp = requests.get(url, headers=_headers(), params=params, verify=True, timeout=10)
        if resp.status_code == 200:
            prs = resp.json().get("values", [])
            # Filter by ticket key in title or description
            matching = []
            for pr in prs:
                title = pr.get("title", "")
                desc = pr.get("description", "") or ""
                if search_text.upper() in title.upper() or search_text.upper() in desc.upper():
                    matching.append(_extract_pr_summary(pr, repo_slug))
            return matching
        return []
    except:
        return []


def _search_repo_commits(repo_slug, search_text):
    """Search commits in a specific repo by message content."""
    try:
        url = (
            f"{config.BITBUCKET_BASE_URL}/rest/api/1.0/projects/"
            f"{config.BITBUCKET_PROJECT}/repos/{repo_slug}/commits"
        )
        params = {"limit": 50}
        resp = requests.get(url, headers=_headers(), params=params, verify=True, timeout=10)
        if resp.status_code == 200:
            commits = resp.json().get("values", [])
            matching = []
            for c in commits:
                msg = c.get("message", "")
                if search_text.upper() in msg.upper():
                    matching.append({
                        "repo": repo_slug,
                        "id": c.get("id", "")[:12],
                        "message": msg[:200],
                        "author": c.get("author", {}).get("name", "Unknown"),
                        "date": c.get("authorTimestamp", ""),
                    })
            return matching
        return []
    except:
        return []


def _extract_pr_summary(pr_data, repo_slug):
    """Extract clean PR summary."""
    return {
        "repo": repo_slug,
        "id": pr_data.get("id"),
        "title": pr_data.get("title", ""),
        "description": (pr_data.get("description", "") or "")[:300],
        "state": pr_data.get("state", ""),
        "author": pr_data.get("author", {}).get("user", {}).get("displayName", "Unknown"),
        "created": pr_data.get("createdDate", ""),
        "updated": pr_data.get("updatedDate", ""),
        "source_branch": pr_data.get("fromRef", {}).get("displayId", ""),
        "target_branch": pr_data.get("toRef", {}).get("displayId", ""),
    }

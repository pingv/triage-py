"""
Configuration for AI Triage Toolkit
====================================
Update these values with your ADP credentials and URLs.
All auth tokens are kept here in one place for easy management.
"""

# =============================================================================
# JIRA Configuration
# =============================================================================
JIRA_BASE_URL = "https://jira.service.tools-pi.com"
JIRA_PAT = "YOUR_JIRA_PAT_HERE"  # Your Personal Access Token

# Projects to search for historical patterns
JIRA_PROJECTS = ["TIMPOLPAY", "TIMSCHED", "TIMEMON", "TIMEFEAT"]

# How many historical tickets to search for similar issues
JIRA_MAX_SIMILAR_RESULTS = 20

# Fields to fetch from JIRA
JIRA_FIELDS = [
    "key", "summary", "description", "status", "resolution",
    "created", "updated", "resolutiondate", "assignee", "reporter",
    "fixVersions", "project", "issuetype", "priority", "labels",
    "components", "comment",  # comments contain resolution details
    "issuelinks",  # linked issues (PRs, related tickets)
]

# =============================================================================
# Confluence Configuration
# =============================================================================
CONFLUENCE_BASE_URL = "https://confluence.service.tools-pi.com"  # UPDATE THIS
CONFLUENCE_PAT = "YOUR_CONFLUENCE_PAT_HERE"

# Spaces to search for relevant documentation
CONFLUENCE_SPACES = ["TIM", "TIMDEV", "TIMOPS"]  # UPDATE with your space keys

# Max pages to pull per search
CONFLUENCE_MAX_RESULTS = 5

# Core L1/L2 knowledge pages - ALWAYS included in every triage
# Add your troubleshooting runbook page IDs here.
# Find the page ID: open the page in Confluence → ... menu → Page Information → ID in URL
# Example: https://confluence.../pages/viewpage.action?pageId=12345678 → "12345678"
CONFLUENCE_CORE_PAGES = [
    # "12345678",  # Common Issues & Troubleshooting Guide
    # "23456789",  # Pay Policy Configuration Runbook
    # "34567890",  # Schedule Management Known Issues
    # Add your page IDs here - these are always fetched regardless of search
]

# =============================================================================
# Bitbucket Configuration
# =============================================================================
BITBUCKET_BASE_URL = "https://bitbucket.service.tools-pi.com"  # UPDATE THIS
BITBUCKET_PAT = "YOUR_BITBUCKET_PAT_HERE"

# Projects/repos to search
BITBUCKET_PROJECT = "TIM"  # UPDATE with your Bitbucket project key
BITBUCKET_REPOS = []  # Leave empty to search all repos in project

# =============================================================================
# AI Configuration
# =============================================================================
# How to invoke Amazon Q CLI - update based on your setup
# Common options: "q chat", "amazon-q", "q"
AMAZON_Q_COMMAND = "q chat"

# AI mode: "auto" (try to script Amazon Q), "manual" (print prompt for copy-paste)
AI_MODE = "manual"  # Start with manual, switch to "auto" once you test Amazon Q

# =============================================================================
# Local Storage
# =============================================================================
# All paths are relative to the toolkit directory
KNOWLEDGE_DIR = "knowledge"
CACHE_DIR = "cache"
OUTPUT_DIR = "output"

# How old cached data can be before re-fetching (in hours)
CACHE_TTL_HOURS = 24

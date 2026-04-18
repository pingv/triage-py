#!/usr/bin/env python3
"""
AI Triage Toolkit - Main Entry Point
=====================================
Usage:
    python triage.py TIMEFEAT-101              # Full triage of a ticket
    python triage.py --load-response TIMEFEAT-101  # Load AI response from file
    python triage.py --stats                   # Show knowledge base stats
    python triage.py --test-connections        # Test all API connections

Author: Pinggru @ ADP
Purpose: AI-powered production support triage using local resources
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Ensure we're running from the toolkit directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import config
import jira_client
import confluence_client
import bitbucket_client
import knowledge_manager
import prompt_builder
import ai_engine


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║               AI TRIAGE TOOLKIT  v1.0                       ║
║          Production Support Issue Analysis                   ║
╚══════════════════════════════════════════════════════════════╝
""")
    print(f"  Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    stats = knowledge_manager.get_knowledge_stats()
    print(f"  Knowledge : {stats['total_analyses']} analyses, {stats['total_patterns']} patterns")
    print()


def test_connections():
    """Test connectivity to all services."""
    print("Testing connections...\n")
    results = {}

    print("  JIRA:")
    results["jira"] = jira_client.test_connection()

    print("  Confluence:")
    results["confluence"] = confluence_client.test_connection()

    print("  Bitbucket:")
    results["bitbucket"] = bitbucket_client.test_connection()

    print()
    working = sum(1 for v in results.values() if v)
    print(f"  Result: {working}/3 services connected")
    if not results["jira"]:
        print("  ⚠ JIRA is required. Check your PAT in config.py")
    if not results["confluence"]:
        print("  ℹ Confluence is optional - triage will work without it")
    if not results["bitbucket"]:
        print("  ℹ Bitbucket is optional - triage will work without it")
    return results


def triage_ticket(ticket_key):
    """
    Full triage pipeline for a single ticket.
    """
    print(f"{'='*60}")
    print(f"  TRIAGING: {ticket_key}")
    print(f"{'='*60}\n")

    # ------------------------------------------------------------------
    # Step 0: Check if we already analyzed this ticket
    # ------------------------------------------------------------------
    print("Step 0: Checking knowledge base...")
    previous = knowledge_manager.find_previous_analysis(ticket_key)
    if previous:
        print(f"  ℹ Found previous analysis from {previous.get('timestamp', '?')}")
        print(f"  Do you want to re-analyze? The previous results are in the output folder.")
        # Continue anyway - re-analysis with fresh data may find new context

    # ------------------------------------------------------------------
    # Step 1: Fetch the target ticket from JIRA
    # ------------------------------------------------------------------
    print("\nStep 1: Fetching ticket from JIRA...")
    raw_ticket = jira_client.fetch_ticket(ticket_key)
    if not raw_ticket:
        print(f"\n  ✗ Could not fetch {ticket_key}. Aborting.")
        print(f"    Check that the ticket exists and your PAT is valid.")
        return False

    ticket = jira_client.extract_ticket_summary(raw_ticket)
    print(f"  ✓ {ticket['key']}: {ticket['summary']}")
    print(f"    Status: {ticket['status']} | Assignee: {ticket['assignee']}")

    # ------------------------------------------------------------------
    # Step 2: Search local knowledge for similar past analyses
    # ------------------------------------------------------------------
    print("\nStep 2: Searching local knowledge base...")
    similar_analyses = knowledge_manager.find_similar_analyses(ticket["summary"])
    if similar_analyses:
        print(f"  ✓ Found {len(similar_analyses)} similar past analyses")
        for sa in similar_analyses[:3]:
            print(f"    → {sa['ticket_key']} (similarity: {sa['similarity']})")
    else:
        print("  ℹ No similar past analyses found (knowledge base will grow over time)")

    # Search for matching patterns
    keywords = ticket["summary"].split()
    known_patterns = knowledge_manager.search_patterns(keywords)
    if known_patterns:
        print(f"  ✓ Found {len(known_patterns)} matching patterns")

    # ------------------------------------------------------------------
    # Step 3: Search JIRA for similar historical tickets
    # ------------------------------------------------------------------
    print("\nStep 3: Searching JIRA for similar historical tickets...")
    similar_tickets = jira_client.search_similar_tickets(
        ticket["summary"],
        ticket["description"],
        exclude_key=ticket_key,
    )

    # Also search for tickets linked to the same issues
    for link in ticket.get("linked_issues", []):
        linked_key = link.get("key", "")
        if linked_key:
            linked_ticket = jira_client.fetch_ticket(linked_key)
            # Just fetch for context, the linked tickets themselves are informative

    # ------------------------------------------------------------------
    # Step 4: Search Confluence for relevant documentation
    # ------------------------------------------------------------------
    print("\nStep 4: Searching Confluence for relevant knowledge...")
    confluence_pages = []
    try:
        # Search by ticket TOPIC/SYMPTOMS, not by ticket key
        confluence_pages = confluence_client.search_pages(
            ticket["summary"],
            ticket["description"],
        )
    except Exception as e:
        print(f"  ⚠ Confluence search skipped: {e}")

    # ------------------------------------------------------------------
    # Step 5: Search Bitbucket for code changes from SIMILAR tickets
    # ------------------------------------------------------------------
    print("\nStep 5: Searching Bitbucket for related code changes...")
    bitbucket_prs = []
    bitbucket_commits = []
    try:
        # A new ticket won't have PRs — the VALUE is in finding PRs
        # from the SIMILAR historical tickets that were already resolved.
        # Those PRs show what code was changed to fix similar problems.

        if similar_tickets:
            searched_keys = set()
            for st in similar_tickets[:5]:  # Top 5 similar tickets
                st_key = st.get("key", "")
                if st_key and st_key not in searched_keys:
                    searched_keys.add(st_key)
                    prs = bitbucket_client.search_prs_by_ticket(st_key)
                    commits = bitbucket_client.search_commits_by_ticket(st_key)
                    bitbucket_prs.extend(prs)
                    bitbucket_commits.extend(commits)

            if bitbucket_prs or bitbucket_commits:
                print(f"  ✓ Total: {len(bitbucket_prs)} PRs, {len(bitbucket_commits)} commits from similar tickets")
            else:
                print(f"  ℹ No PRs/commits found for similar tickets")
        else:
            print("  ℹ No similar tickets found, skipping Bitbucket search")

        # Also check if the new ticket itself has any linked PRs (rare but possible)
        new_ticket_prs = bitbucket_client.search_prs_by_ticket(ticket_key)
        if new_ticket_prs:
            print(f"  ✓ Also found {len(new_ticket_prs)} PRs for {ticket_key} itself")
            bitbucket_prs.extend(new_ticket_prs)

    except Exception as e:
        print(f"  ⚠ Bitbucket search skipped: {e}")

    # ------------------------------------------------------------------
    # Step 6: Build the AI prompt
    # ------------------------------------------------------------------
    print("\nStep 6: Assembling AI prompt...")

    # Load domain knowledge (synonyms, routing rules, false patterns)
    domain_knowledge = None
    dk_file = os.path.join(config.KNOWLEDGE_DIR, "domain_knowledge.json")
    if os.path.exists(dk_file):
        try:
            with open(dk_file, "r") as f:
                domain_knowledge = json.load(f)
            print(f"  ✓ Loaded domain knowledge (synonyms, routing, false patterns)")
        except Exception as e:
            print(f"  ⚠ Could not load domain_knowledge.json: {e}")

    prompt = prompt_builder.build_triage_prompt(
        ticket_summary=ticket,
        similar_tickets=similar_tickets,
        confluence_pages=confluence_pages,
        bitbucket_prs=bitbucket_prs,
        bitbucket_commits=bitbucket_commits,
        prior_analyses=similar_analyses,
        known_patterns=known_patterns,
        domain_knowledge=domain_knowledge,
    )
    print(f"  ✓ Prompt assembled ({len(prompt)} chars, ~{len(prompt.split())} words)")

    # ------------------------------------------------------------------
    # Step 7: Run AI analysis
    # ------------------------------------------------------------------
    print("\nStep 7: Running AI analysis...")
    analysis = ai_engine.run_analysis(prompt, ticket_key)

    # ------------------------------------------------------------------
    # Step 8: Save results
    # ------------------------------------------------------------------
    if analysis:
        print("\nStep 8: Saving results...")
        knowledge_manager.save_analysis(ticket_key, {
            "summary": ticket["summary"],
            "description": ticket["description"],
            "similar_tickets": [st.get("key", "") for st in (similar_tickets or [])],
            "ai_analysis": analysis,
            "confidence": "pending_review",
        })

        # Save the full triage report
        report_file = os.path.join(config.OUTPUT_DIR, f"triage_{ticket_key}.txt")
        with open(report_file, "w") as f:
            f.write(f"TRIAGE REPORT: {ticket_key}\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write(f"{'='*60}\n\n")
            f.write(analysis)
        print(f"  ✓ Triage report saved to: {report_file}")

        print(f"\n{'='*60}")
        print(f"  ✓ TRIAGE COMPLETE FOR {ticket_key}")
        print(f"{'='*60}")
    else:
        print("\nStep 8: Awaiting AI response...")
        print(f"  Follow the instructions above to complete the analysis.")
        print(f"  Then run: python triage.py --load-response {ticket_key}")

    return True


def load_response_and_save(ticket_key):
    """
    Load an AI response from file and save it to the knowledge base.
    Used when running in manual mode.
    """
    print(f"Loading AI response for {ticket_key}...\n")

    analysis = ai_engine.load_response(ticket_key)
    if not analysis:
        return False

    # Try to load the original ticket summary for context
    raw_ticket = jira_client.fetch_ticket(ticket_key)
    summary = ""
    description = ""
    if raw_ticket:
        ticket = jira_client.extract_ticket_summary(raw_ticket)
        summary = ticket.get("summary", "")
        description = ticket.get("description", "")

    # Save to knowledge base
    knowledge_manager.save_analysis(ticket_key, {
        "summary": summary,
        "description": description,
        "similar_tickets": [],
        "ai_analysis": analysis,
        "confidence": "pending_review",
    })

    # Save the full triage report
    report_file = os.path.join(config.OUTPUT_DIR, f"triage_{ticket_key}.txt")
    with open(report_file, "w") as f:
        f.write(f"TRIAGE REPORT: {ticket_key}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"{'='*60}\n\n")
        f.write(analysis)

    print(f"\n  ✓ Analysis saved to knowledge base")
    print(f"  ✓ Triage report: {report_file}")
    print(f"\n  The system will use this analysis to help triage similar future tickets.")
    return True


def show_stats():
    """Show knowledge base statistics."""
    stats = knowledge_manager.get_knowledge_stats()
    print("Knowledge Base Statistics")
    print(f"{'─'*40}")
    print(f"  Total Analyses : {stats['total_analyses']}")
    print(f"  Total Patterns : {stats['total_patterns']}")

    # List recent analyses
    analyses = knowledge_manager._load_json(knowledge_manager.ANALYSES_FILE)
    if analyses:
        print(f"\n  Recent Analyses:")
        sorted_analyses = sorted(
            analyses.items(),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True,
        )
        for key, data in sorted_analyses[:10]:
            ts = data.get("timestamp", "?")[:16]
            summary = data.get("summary", "")[:50]
            print(f"    {ts} | {key}: {summary}")


def main():
    parser = argparse.ArgumentParser(
        description="AI Triage Toolkit - Production Support Issue Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python triage.py TIMEFEAT-101              # Triage a ticket
  python triage.py --load-response TIMEFEAT-101  # Load AI response
  python triage.py --test-connections        # Test API access
  python triage.py --stats                   # Show knowledge stats
        """,
    )
    parser.add_argument("ticket", nargs="?", help="JIRA ticket key to triage (e.g., TIMEFEAT-101)")
    parser.add_argument("--load-response", metavar="TICKET", help="Load saved AI response for a ticket")
    parser.add_argument("--test-connections", action="store_true", help="Test all API connections")
    parser.add_argument("--stats", action="store_true", help="Show knowledge base statistics")

    args = parser.parse_args()

    print_banner()

    if args.test_connections:
        test_connections()
    elif args.stats:
        show_stats()
    elif args.load_response:
        load_response_and_save(args.load_response)
    elif args.ticket:
        triage_ticket(args.ticket)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

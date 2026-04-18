"""
AI Engine - Interfaces with Amazon Q CLI or provides manual prompt mode
Designed to be swappable: if Amazon Q can be scripted, uses auto mode.
Otherwise, prints the prompt for copy-paste.
"""

import os
import subprocess
import tempfile
from datetime import datetime

import config


def run_analysis(prompt, ticket_key):
    """
    Send the prompt to the AI and return the analysis.
    Tries auto mode first, falls back to manual if needed.
    """
    if config.AI_MODE == "auto":
        return _run_auto(prompt, ticket_key)
    else:
        return _run_manual(prompt, ticket_key)


def _run_auto(prompt, ticket_key):
    """
    Attempt to pipe the prompt to Amazon Q CLI.
    If this doesn't work on your setup, switch AI_MODE to "manual" in config.py
    """
    print("\n  🤖 Sending to Amazon Q CLI...")

    # Write prompt to a temp file
    prompt_file = os.path.join(config.OUTPUT_DIR, f"prompt_{ticket_key}.txt")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    try:
        # Attempt 1: pipe via stdin
        result = subprocess.run(
            config.AMAZON_Q_COMMAND.split(),
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )

        if result.returncode == 0 and result.stdout.strip():
            analysis = result.stdout.strip()
            print(f"  ✓ AI analysis received ({len(analysis)} chars)")
            _save_output(ticket_key, prompt, analysis)
            return analysis
        else:
            print(f"  ⚠ Amazon Q returned no output or failed (code: {result.returncode})")
            if result.stderr:
                print(f"    stderr: {result.stderr[:200]}")
            print("  → Falling back to manual mode")
            return _run_manual(prompt, ticket_key)

    except subprocess.TimeoutExpired:
        print("  ⚠ Amazon Q timed out after 120 seconds")
        print("  → Falling back to manual mode")
        return _run_manual(prompt, ticket_key)
    except FileNotFoundError:
        print(f"  ⚠ Command '{config.AMAZON_Q_COMMAND}' not found")
        print("  → Falling back to manual mode")
        return _run_manual(prompt, ticket_key)
    except Exception as e:
        print(f"  ⚠ Error running Amazon Q: {e}")
        print("  → Falling back to manual mode")
        return _run_manual(prompt, ticket_key)


def _run_manual(prompt, ticket_key):
    """
    Manual mode: save the prompt to a file and display instructions.
    User copies the prompt into Amazon Q (or any AI), then pastes the
    response back (or saves it to a file).
    """
    # Save prompt to file
    prompt_file = os.path.join(config.OUTPUT_DIR, f"prompt_{ticket_key}.txt")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    response_file = os.path.join(config.OUTPUT_DIR, f"response_{ticket_key}.txt")

    print("\n" + "=" * 80)
    print("  📋  MANUAL AI MODE")
    print("=" * 80)
    print(f"""
  The research is done! All context has been gathered and assembled.

  PROMPT SAVED TO: {prompt_file}
  Prompt length: {len(prompt)} characters (~{len(prompt.split())} words)

  NEXT STEPS:
  ─────────────────────────────────────────────────────────
  Option A — Copy-paste into Amazon Q CLI:
    1. Open a new terminal
    2. Run: q chat
    3. Copy contents of: {prompt_file}
    4. Paste into Amazon Q
    5. Save the AI response to: {response_file}
    6. Run: python triage.py --load-response {ticket_key}

  Option B — Use any AI chat (Claude, ChatGPT, etc):
    1. Open the prompt file: {prompt_file}
    2. Copy all contents
    3. Paste into the AI chat
    4. Save the AI response to: {response_file}
    5. Run: python triage.py --load-response {ticket_key}
  ─────────────────────────────────────────────────────────
""")

    # Check if response file already exists (maybe from a previous run)
    if os.path.exists(response_file):
        print(f"  📄 Found existing response file: {response_file}")
        with open(response_file, "r") as f:
            analysis = f.read().strip()
        if analysis:
            print(f"  ✓ Loaded previous AI response ({len(analysis)} chars)")
            return analysis

    return None


def load_response(ticket_key):
    """
    Load an AI response that was saved manually by the user.
    Called via: python triage.py --load-response TIMEFEAT-101
    """
    response_file = os.path.join(config.OUTPUT_DIR, f"response_{ticket_key}.txt")

    if not os.path.exists(response_file):
        print(f"  ✗ Response file not found: {response_file}")
        print(f"    Save the AI response to this file and try again.")
        return None

    with open(response_file, "r") as f:
        analysis = f.read().strip()

    if not analysis:
        print(f"  ✗ Response file is empty: {response_file}")
        return None

    print(f"  ✓ Loaded AI response from {response_file} ({len(analysis)} chars)")
    return analysis


def _save_output(ticket_key, prompt, analysis):
    """Save both prompt and response for audit trail."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    prompt_file = os.path.join(config.OUTPUT_DIR, f"prompt_{ticket_key}.txt")
    response_file = os.path.join(config.OUTPUT_DIR, f"response_{ticket_key}.txt")

    with open(prompt_file, "w") as f:
        f.write(prompt)

    with open(response_file, "w") as f:
        f.write(analysis)

    print(f"  💾 Prompt saved to: {prompt_file}")
    print(f"  💾 Response saved to: {response_file}")

# AI Triage Toolkit

**AI-powered production support triage for ADP Time & Attendance**

This toolkit automatically gathers context from JIRA, Confluence, and Bitbucket,
assembles it into a structured prompt, and feeds it to an AI for analysis.
It builds a local knowledge base that gets smarter with every ticket you triage.

---

## Quick Start (5 minutes)

### 1. Unzip and enter the directory
```bash
cd ai-triage-toolkit
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
# or if you need:
pip3 install -r requirements.txt
```

### 3. Configure your credentials
Edit `config.py` and update:
- `JIRA_PAT` — your JIRA Personal Access Token (you already have this)
- `CONFLUENCE_PAT` — your Confluence PAT
- `BITBUCKET_PAT` — your Bitbucket PAT
- Base URLs if they differ from defaults

### 4. Test connections
```bash
python triage.py --test-connections
```

### 5. Triage your first ticket
```bash
python triage.py TIMEFEAT-101
```

---

## How It Works

```
You run:  python triage.py TIMEFEAT-101
                    │
  Step 1: Fetch ticket details from JIRA
  Step 2: Check local knowledge base for similar past analyses
  Step 3: Search JIRA for similar resolved historical tickets
  Step 4: Search Confluence for relevant documentation
  Step 5: Search Bitbucket for related PRs and commits
  Step 6: Assemble everything into a structured AI prompt
  Step 7: Send to Amazon Q (or save prompt for manual copy-paste)
  Step 8: Save results to local knowledge base
                    │
Output:  Structured triage analysis + knowledge base updated
```

---

## Usage

### Triage a ticket
```bash
python triage.py TIMEFEAT-101
python triage.py TIMPOLPAY-250
python triage.py TIMSCHED-88
```

### Manual AI mode (default)
When `AI_MODE = "manual"` in config.py (the default), the script:
1. Does all the research (JIRA, Confluence, Bitbucket)
2. Saves the assembled prompt to `output/prompt_TIMEFEAT-101.txt`
3. You copy that prompt into Amazon Q CLI (or any AI)
4. You save the AI response to `output/response_TIMEFEAT-101.txt`
5. You run:
```bash
python triage.py --load-response TIMEFEAT-101
```
This saves the response to the knowledge base for future reference.

### Auto AI mode
If Amazon Q CLI supports piping (test with `echo "hello" | q chat`):
1. Set `AI_MODE = "auto"` in config.py
2. Set `AMAZON_Q_COMMAND` to the correct command
3. The script will automatically send the prompt and capture the response

### Check knowledge base stats
```bash
python triage.py --stats
```

### Test API connections
```bash
python triage.py --test-connections
```

---

## Project Structure

```
ai-triage-toolkit/
├── triage.py              # Main entry point — run this
├── config.py              # All configuration and credentials
├── jira_client.py         # JIRA API integration
├── confluence_client.py   # Confluence API integration
├── bitbucket_client.py    # Bitbucket API integration
├── prompt_builder.py      # Assembles context into AI prompt
├── ai_engine.py           # Handles AI interaction (auto/manual)
├── knowledge_manager.py   # Local knowledge storage and retrieval
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── knowledge/             # AI's memory (grows over time)
│   ├── analyses.json      # Every triage analysis stored here
│   └── patterns.json      # Extracted recurring patterns
├── cache/                 # API response cache (auto-managed)
│   ├── tickets/           # Cached JIRA ticket data
│   ├── confluence/        # Cached Confluence pages
│   └── bitbucket/         # Cached Bitbucket data
└── output/                # Triage outputs
    ├── prompt_*.txt       # Generated prompts
    ├── response_*.txt     # AI responses
    └── triage_*.txt       # Final triage reports
```

---

## The Knowledge Base

The toolkit builds a local "second brain" that gets smarter over time:

- **analyses.json** — Every ticket you triage is stored here. When a new
  ticket comes in, the system checks if it's seen something similar before
  and includes that context in the AI prompt.

- **patterns.json** — You can manually add recurring patterns here, or the
  AI will suggest new patterns in its analysis output (Section 8). Over time,
  this becomes a machine-readable runbook.

### Adding a pattern manually
```json
{
  "PAT-0001": {
    "pattern_id": "PAT-0001",
    "category": "overtime_calculation_mismatch",
    "symptoms": ["overtime hours wrong", "weekly OT not applied"],
    "root_causes": ["Pay rule missing weekly OT threshold"],
    "resolution_steps": ["Check pay rule config", "Verify OT thresholds"],
    "times_seen": 5
  }
}
```

---

## Tips

- **Start with 5-10 recently resolved tickets** to seed the knowledge base.
  Triage them even though they're resolved — this builds the pattern library.

- **Confluence and Bitbucket are optional.** The system works with JIRA only.
  The other integrations add richness but aren't required.

- **The cache saves API calls.** Ticket data is cached for 24 hours by default.
  Change `CACHE_TTL_HOURS` in config.py if needed.

- **For the leadership demo:** Run 5 tickets, compare AI analysis vs actual
  resolution. Side-by-side comparison is the most convincing format.

---

## FAQ

**Q: Does this need internet/cloud access?**
A: It needs network access to your ADP JIRA/Confluence/Bitbucket instances.
Everything else (knowledge base, AI prompt assembly) is 100% local.

**Q: Does this modify any JIRA tickets?**
A: No. This toolkit is completely read-only. It never writes to JIRA,
Confluence, or Bitbucket. It only reads.

**Q: What if I don't have Confluence or Bitbucket access?**
A: That's fine. The script will show a warning and skip those steps.
JIRA alone provides 70% of the value.

**Q: How do I test Amazon Q CLI scripting?**
A: Run: `echo "What is 2+2?" | q chat`
If you get a response, set AI_MODE to "auto" in config.py.

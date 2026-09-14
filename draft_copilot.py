import os
import sys
import re
import time
import json
from datetime import datetime
from collections import Counter
from espn_api.football import League
from google import genai
from google.genai import types
from google.genai.errors import ServerError
from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv()

LEAGUE_ID = int(os.environ.get("ESPN_LEAGUE_ID", 0))
YEAR = int(os.environ.get("ESPN_YEAR", 2026))
ESPN_S2 = os.environ.get("ESPN_S2", "")
SWID = os.environ.get("SWID", "")

MY_TEAM_NAME = os.environ.get("ESPN_TEAM_NAME", "Team Name")
POLL_INTERVAL_SEC = 4
TOTAL_LEAGUE_TEAMS = 12
HTML_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "draft_dashboard.html")
# =================================================

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    sys.exit("Error: GEMINI_API_KEY environment variable is not set.")

client = genai.Client(api_key=api_key)
MODELS_CASCADE = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]

class DraftRecommendation(BaseModel):
    primary_target: str = Field(description="Best player to draft right now, with position and NFL team.")
    backup_target: str = Field(description="Immediate pivot option if primary target is sniped.")
    cliff_warning: str = Field(description="Alert regarding any imminent tier cliff or run before our next turn.")
    turn_gap_threat: str = Field(description="Assessment of what opponents picking before our next turn will target.")
    rationale: str = Field(description="Analytical justification incorporating recent news/injury status.")
    verified_news: str = Field(default="No red flags found.", description="Brief note on verified health or depth chart status.")

# Enable native Google Search tool (without response_mime_type to avoid 400 error)
GENAI_CONFIG = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())],
    temperature=0.15
)

def clean_and_parse_json(text):
    """Strips markdown fences and parses into DraftRecommendation."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
        return DraftRecommendation(**data)
    except Exception as e:
        # Fallback regex if slight formatting aberration occurs
        return DraftRecommendation(
            primary_target="Target parsing error",
            backup_target="N/A",
            cliff_warning="N/A",
            turn_gap_threat="N/A",
            rationale=cleaned[:180],
            verified_news="Parse fallback"
        )

def generate_with_fallback(prompt):
    for model_name in MODELS_CASCADE:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=GENAI_CONFIG
            )
            
            # Extract search queries if Gemini invoked Google Search
            search_queries = []
            try:
                candidate = res.candidates[0]
                metadata = getattr(candidate, "grounding_metadata", None)
                if metadata and hasattr(metadata, "web_search_queries") and metadata.web_search_queries:
                    search_queries = metadata.web_search_queries
            except Exception:
                pass

            parsed_obj = clean_and_parse_json(res.text)
            return parsed_obj, model_name, search_queries

        except ServerError as e:
            if "503" in str(e):
                print(f"   [Notice: {model_name} busy (503). Failing over...]")
                time.sleep(0.4)
                continue
            raise e
        except Exception as e:
            print(f"   [Notice: {model_name} failed: {e}. Trying fallback...]")
            continue

    return None, "none", []

def get_my_team_and_slot(league, target_name):
    for idx, team in enumerate(league.teams):
        if team.team_name.strip().lower() == target_name.strip().lower():
            slot = getattr(team, 'draft_position', idx + 1)
            return team, slot
    return league.teams[0], 1

def get_gap_roster_needs(league, current_pick, my_slot, num_teams):
    gap_teams = []
    next_pick = current_pick
    
    while True:
        rd = (next_pick - 1) // num_teams + 1
        pos = (next_pick - 1) % num_teams + 1
        slot = pos if rd % 2 == 1 else (num_teams - pos + 1)
        
        if slot == my_slot and next_pick != current_pick:
            break
        if slot != my_slot:
            gap_teams.append(slot)
            
        next_pick += 1
        if next_pick > current_pick + 30:
            break
            
    needs = {"QB": 0, "TE": 0, "DST": 0}
    for team in league.teams:
        team_slot = getattr(team, 'draft_position', 0)
        if team_slot in gap_teams:
            roster_positions = [p.position for p in team.roster]
            picks_for_team = gap_teams.count(team_slot)
            if "QB" not in roster_positions:
                needs["QB"] += picks_for_team
            if "TE" not in roster_positions:
                needs["TE"] += picks_for_team
            if "D/ST" not in roster_positions:
                needs["DST"] += picks_for_team
                
    return len(gap_teams), needs

def is_my_turn_or_on_deck(pick_num, slot, num_teams):
    def get_slot(p):
        rd = (p - 1) // num_teams + 1
        pos = (p - 1) % num_teams + 1
        return pos if rd % 2 == 1 else (num_teams - pos + 1)

    return (get_slot(pick_num) == slot), (get_slot(pick_num + 1) == slot)

def slice_available_pool(raw_available):
    pos_limits = {"QB": 4, "RB": 6, "WR": 6, "TE": 4, "D/ST": 3, "K": 2}
    pos_counts = {k: 0 for k in pos_limits}
    available_summary = []
    structured_board = []
    
    for p in raw_available:
        pos = getattr(p, 'position', 'FLEX')
        if pos in pos_limits and pos_counts[pos] < pos_limits[pos]:
            proj = getattr(p, 'projected_total_points', 0.0)
            team = getattr(p, 'proTeam', 'FA')
            status = getattr(p, 'injuryStatus', 'ACTIVE')
            bye = getattr(p, 'on_bye_week', 0)
            
            available_summary.append(f"- {p.name} ({team} - {pos} | Proj: {proj:.1f} | Status: {status} | Bye: {bye})")
            structured_board.append({
                "name": p.name, 
                "pos": pos, 
                "proj": f"{proj:.1f}",
                "team": team,
                "status": status,
                "bye": bye
            })
            pos_counts[pos] += 1
    return available_summary, structured_board

def query_gemini_strategy(league, my_team, current_picks, raw_available, upcoming_pick_num, my_slot):
    settings = league.settings
    slot_counts = getattr(settings, "position_slot_counts", {})
    scoring_type = getattr(settings, "scoring_type", "PPR / Standard")

    my_positions = [p.position for p in my_team.roster]
    pos_counts = Counter(my_positions)
    roster_detail = [f"{p.name} ({p.position})" for p in my_team.roster]
    
    starting_slots = {k: v for k, v in slot_counts.items() if k not in ["BE", "IR", "FLEX"] and v > 0}
    deficits = []
    for pos, needed in starting_slots.items():
        have = pos_counts.get(pos, 0)
        if have < needed:
            deficits.append(f"Need {needed - have} {pos}")
    deficit_str = ", ".join(deficits) if deficits else "Starting lineup positions filled. Drafting for depth/value."

    turn_gap, gap_needs = get_gap_roster_needs(league, upcoming_pick_num, my_slot, TOTAL_LEAGUE_TEAMS)
    round_num = ((upcoming_pick_num - 1) // TOTAL_LEAGUE_TEAMS) + 1
    last_8_picks = [f"{p.playerName} (Rd {p.round_num})" for p in current_picks[-8:]]
    available_summary, structured_board = slice_available_pool(raw_available)

    prompt = f"""
You are an expert game-theory Fantasy Football strategist with live Google Search capabilities.

DRAFT STATE:
- Pick Number: #{upcoming_pick_num} (Round {round_num})
- Draft Slot: #{my_slot} | Gap until next turn: {turn_gap} picks
- League: {settings.team_count} Teams, {scoring_type}, Slots: {slot_counts}

MY CURRENT ROSTER:
- Position Counts: {dict(pos_counts)}
- Players: {", ".join(roster_detail) if roster_detail else "Empty (First Pick)"}
- Roster Needs: {deficit_str}

OPPONENT NEEDS IN THE GAP ({turn_gap} picks until our next turn):
- Teams in gap need: {gap_needs['QB']} QBs, {gap_needs['TE']} TEs, {gap_needs['DST']} D/STs

RECENT BOARD PICKS:
{", ".join(last_8_picks) if last_8_picks else "Draft starting"}

TOP AVAILABLE CANDIDATES:
{chr(10).join(available_summary)}

CRITICAL SEARCH & INJURY DIRECTIVE:
1. The 'Status' field provided in the candidates list is the HARD TRUTH from ESPN (e.g. ACTIVE, QUESTIONABLE, OUT, IR).
2. DO NOT use Google Search to guess if a player is injured. ONLY use Google Search to get context on a player already marked as QUESTIONABLE/OUT/IR, or to check recent training camp depth-chart news.
3. DO NOT recommend any player with Status: OUT or IR unless it is an explicitly identified deep bench stash.

OUTPUT FORMAT REQUIREMENTS:
Output ONLY a valid JSON object matching these exact keys with no extra text or conversational filler:
{{
  "primary_target": "Player Name (POS, TEAM)",
  "backup_target": "Player Name (POS, TEAM)",
  "cliff_warning": "Imminent positional tier cliff before next turn",
  "turn_gap_threat": "Opponent roster analysis in the gap",
  "rationale": "Game-theory justification",
  "verified_news": "Confirmed live news/health status via Google Search"
}}
"""
    rec, model_used, search_queries = generate_with_fallback(prompt)
    return rec, model_used, search_queries, turn_gap, gap_needs, structured_board

def render_html_dashboard(league, my_team, my_slot, next_pick_num, is_clock, is_deck, rec, model_used, search_queries, turn_gap, gap_needs, structured_board):
    now_str = datetime.now().strftime("%I:%M:%S %p")
    round_num = ((next_pick_num - 1) // TOTAL_LEAGUE_TEAMS) + 1

    if is_clock:
        status_badge = '<span class="badge badge-clock animate-pulse">🚨 ON THE CLOCK</span>'
    elif is_deck:
        status_badge = '<span class="badge badge-deck">👀 ON DECK (1 PICK AWAY)</span>'
    else:
        status_badge = '<span class="badge badge-idle">⏳ WAITING FOR TURN</span>'

    roster_rows = ""
    for p in my_team.roster:
        roster_rows += f"""
        <div class="roster-item">
            <span class="pos-tag pos-{p.position.lower()}">{p.position}</span>
            <span class="player-name">{p.name}</span>
        </div>
        """
    if not my_team.roster:
        roster_rows = '<div class="empty-state">No players drafted yet.</div>'

    board_rows = ""
    for p in structured_board[:18]:
        status_tag = f'<span style="font-size: 9px; color: #ef4444; font-weight: bold; margin-left: 6px;">[{p["status"]}]</span>' if p.get("status") and p["status"] not in ["ACTIVE", "NORMAL"] else ""
        team = p.get('team', 'FA')
        board_rows += f"""
        <div class="board-item">
            <div class="board-item-left">
                <span class="pos-tag pos-{p['pos'].lower()}">{p['pos']}</span>
                <span class="player-name">{p['name']} <small style="color: #64748b; font-size: 10px;">{team}</small>{status_tag}</span>
            </div>
            <span class="proj-pts">{p['proj']} <small>PTS</small></span>
        </div>
        """

    primary = rec.primary_target if rec else "Auditing live board..."
    backup = rec.backup_target if rec else "Auditing live board..."
    cliff = rec.cliff_warning if rec else "Auditing tier cliff dynamics..."
    threat = rec.turn_gap_threat if rec else "Assessing opponent rosters in gap..."
    rationale = rec.rationale if rec else "Synthesizing game-theory strategy..."
    news = rec.verified_news if rec else "Checking live Google Search wire..."

    search_tags = "".join([f'<span class="search-tag">🔍 {q}</span>' for q in search_queries]) if search_queries else '<span style="color:#64748b; font-size:12px;">Using verified NFL news feed</span>'

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="{POLL_INTERVAL_SEC}">
    <title>Draft Copilot | {my_team.team_name}</title>
    <script>
        // Apply theme immediately to prevent flash
        const savedTheme = localStorage.getItem('copilotTheme') || 'theme-cyberpunk';
        document.documentElement.className = savedTheme;
        
        function setTheme(theme) {{
            localStorage.setItem('copilotTheme', theme);
            document.documentElement.className = theme;
            document.getElementById('theme-select').value = theme;
        }}
    </script>
    <style>
        :root, html.theme-cyberpunk {{
            --bg-base: #0a0e17;
            --bg-card: #121826;
            --bg-card-alt: #182234;
            --border-color: #1e293b;
            --border-style: solid;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-blue: #38bdf8;
            --accent-purple: #818cf8;
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --radius: 12px;
            --shadow: none;
            --card-border-width: 1px;
            --item-radius: 8px;
            --header-bg: transparent;
        }}
        
        html.theme-professional {{
            --bg-base: #f1f5f9;
            --bg-card: #ffffff;
            --bg-card-alt: #f8fafc;
            --border-color: #cbd5e1;
            --border-style: solid;
            --text-main: #0f172a;
            --text-muted: #475569;
            --accent-green: #059669;
            --accent-amber: #d97706;
            --accent-blue: #2563eb;
            --accent-purple: #6d28d9;
            --font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
            --radius: 6px;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            --card-border-width: 1px;
            --item-radius: 4px;
            --header-bg: transparent;
        }}
        
        html.theme-y2k {{
            --bg-base: #008080;
            --bg-card: #c0c0c0;
            --bg-card-alt: #ffffff;
            --border-color: #dfdfdf;
            --border-style: outset;
            --text-main: #000000;
            --text-muted: #333333;
            --accent-green: #000080;
            --accent-amber: #800000;
            --accent-blue: #000080;
            --accent-purple: #800080;
            --font-family: "Tahoma", "MS Sans Serif", sans-serif;
            --radius: 0px;
            --shadow: inset -1px -1px #0a0a0a, inset 1px 1px #ffffff, inset -2px -2px #808080, inset 2px 2px #dfdfdf;
            --card-border-width: 2px;
            --item-radius: 0px;
            --header-bg: #000080;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: var(--font-family); }}
        body {{ background-color: var(--bg-base); color: var(--text-main); padding: 24px; transition: background-color 0.2s, color 0.2s; }}
        
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: var(--card-border-width) solid var(--border-color); padding-bottom: 18px; margin-bottom: 24px; }}
        html.theme-y2k .header {{ background: var(--bg-card); padding: 10px; border: var(--card-border-width) outset #fff; box-shadow: var(--shadow); }}
        html.theme-y2k .header-title h1 {{ font-size: 20px; }}
        html.theme-y2k .header-title p {{ color: #000; font-weight: bold; }}
        
        .header-title h1 {{ font-size: 26px; font-weight: 800; }}
        .header-title p {{ color: var(--text-muted); font-size: 14px; margin-top: 4px; }}
        .header-meta {{ display: flex; align-items: center; gap: 14px; }}
        
        .theme-selector {{ padding: 4px 8px; font-size: 12px; border-radius: 4px; background: var(--bg-card); color: var(--text-main); border: 1px solid var(--border-color); }}
        
        .badge {{ padding: 6px 14px; border-radius: 9999px; font-weight: 700; font-size: 13px; text-transform: uppercase; }}
        html.theme-y2k .badge {{ border-radius: 0; border: 2px outset #fff; padding: 2px 6px; font-size: 11px; }}
        
        .badge-clock {{ background: #dc2626; color: #fff; box-shadow: 0 0 16px rgba(220,38,38,0.5); }}
        html.theme-y2k .badge-clock {{ background: #ff0000; box-shadow: none; color: #fff; }}
        
        .badge-deck {{ background: #d97706; color: #fff; }}
        .badge-idle {{ background: var(--bg-card-alt); color: var(--text-muted); border: 1px solid var(--border-color); }}
        .animate-pulse {{ animation: pulse 1.5s infinite; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .6; }} }}
        
        .main-grid {{ display: grid; grid-template-columns: 2fr 1fr; gap: 24px; }}
        @media (max-width: 960px) {{ .main-grid {{ grid-template-columns: 1fr; }} }}
        
        .hero-banner {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
        .target-card {{ background: var(--bg-card); border: var(--card-border-width) var(--border-style) var(--border-color); border-radius: var(--radius); padding: 20px; cursor: pointer; transition: transform 0.1s; box-shadow: var(--shadow); }}
        html.theme-y2k .target-card {{ border-color: #fff; }}
        .target-card:hover {{ transform: translateY(-2px); }}
        html.theme-y2k .target-card:active {{ box-shadow: inset 1px 1px #0a0a0a, inset -1px -1px #ffffff; padding: 21px 19px 19px 21px; }}
        
        .target-card.primary {{ border-color: var(--accent-green); }}
        .target-card.backup {{ border-color: var(--accent-blue); }}
        html.theme-cyberpunk .target-card.primary {{ box-shadow: 0 4px 20px rgba(16,185,129,0.12); }}
        
        .target-label {{ font-size: 11px; text-transform: uppercase; font-weight: 800; letter-spacing: 1px; margin-bottom: 8px; display: block; }}
        .primary .target-label {{ color: var(--accent-green); }}
        .backup .target-label {{ color: var(--accent-blue); }}
        html.theme-y2k .target-label {{ color: #000; font-size: 12px; }}
        
        .target-name {{ font-size: 22px; font-weight: 800; }}
        html.theme-y2k .target-name {{ color: #000080; }}
        
        .card {{ background: var(--bg-card); border: var(--card-border-width) var(--border-style) var(--border-color); border-radius: var(--radius); margin-bottom: 20px; box-shadow: var(--shadow); }}
        html.theme-y2k .card {{ border-color: #fff; }}
        
        .card-header {{ font-size: 13px; font-weight: 700; text-transform: uppercase; color: var(--text-main); margin-bottom: 0; padding: 14px 20px; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; background: var(--header-bg); border-top-left-radius: var(--radius); border-top-right-radius: var(--radius); }}
        html.theme-cyberpunk .card-header {{ color: var(--text-muted); background: transparent; }}
        html.theme-y2k .card-header {{ color: #fff; font-size: 12px; font-weight: bold; padding: 4px 8px; border-bottom: none; }}
        
        .card-body {{ padding: 20px; }}
        html.theme-y2k .card-body {{ padding: 8px; }}
        
        .intel-box {{ display: flex; flex-direction: column; gap: 14px; }}
        .intel-item {{ background: var(--bg-card-alt); border-radius: var(--item-radius); padding: 14px 16px; border-left: 4px solid var(--text-muted); border-top: 1px solid var(--border-color); border-right: 1px solid var(--border-color); border-bottom: 1px solid var(--border-color); }}
        html.theme-y2k .intel-item {{ border: 2px inset #fff; padding: 8px; }}
        
        .intel-item.cliff {{ border-left-color: var(--accent-amber); }}
        .intel-item.threat {{ border-left-color: var(--accent-purple); }}
        .intel-item.rationale {{ border-left-color: var(--accent-green); }}
        .intel-item.news {{ border-left-color: var(--accent-blue); }}
        
        .intel-title {{ font-size: 11px; font-weight: 800; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px; }}
        html.theme-y2k .intel-title {{ color: #000; font-size: 12px; }}
        .intel-body {{ font-size: 14px; line-height: 1.45; }}
        
        .search-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
        .search-tag {{ background: var(--bg-base); border: 1px solid var(--border-color); padding: 3px 8px; border-radius: var(--radius); font-size: 11px; color: var(--accent-blue); }}
        html.theme-y2k .search-tag {{ border-radius: 0; border: 1px solid #808080; color: #000; }}

        .radar-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 12px; }}
        .radar-stat-box {{ background: var(--bg-base); border-radius: var(--item-radius); padding: 10px; text-align: center; border: 1px solid var(--border-color); }}
        html.theme-y2k .radar-stat-box {{ border: 2px inset #fff; background: #fff; }}
        .radar-stat-val {{ font-size: 20px; font-weight: 800; color: var(--accent-blue); }}
        html.theme-y2k .radar-stat-val {{ color: #000; }}
        .radar-stat-lbl {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; margin-top: 2px; }}

        .pos-tag {{ display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 800; margin-right: 8px; color: #fff; min-width: 35px; text-align: center; }}
        html.theme-y2k .pos-tag {{ border-radius: 0; }}
        html.theme-professional .pos-tag {{ border-radius: 2px; font-weight: 700; }}
        
        .pos-qb {{ background: #dc2626; }}
        .pos-rb {{ background: #2563eb; }}
        .pos-wr {{ background: #059669; }}
        .pos-te {{ background: #d97706; }}
        .pos-d/st, .pos-dst {{ background: #475569; }}
        .pos-k {{ background: #64748b; }}

        .roster-grid {{ display: flex; flex-direction: column; gap: 8px; }}
        .roster-item {{ display: flex; align-items: center; background: var(--bg-card-alt); padding: 8px 12px; border-radius: var(--item-radius); font-size: 13px; font-weight: 600; border: 1px solid var(--border-color); }}
        html.theme-y2k .roster-item {{ border: 1px solid #808080; }}
        
        .board-list {{ display: flex; flex-direction: column; gap: 6px; max-height: 480px; overflow-y: auto; }}
        .board-item {{ display: flex; justify-content: space-between; align-items: center; background: var(--bg-card-alt); padding: 8px 12px; border-radius: var(--item-radius); font-size: 13px; border: 1px solid var(--border-color); }}
        html.theme-y2k .board-item {{ border: 1px solid #808080; }}
        
        .board-item-left {{ display: flex; align-items: center; }}
        .proj-pts {{ font-size: 12px; font-weight: 700; color: var(--accent-green); }}
        .proj-pts small {{ font-size: 9px; color: var(--text-muted); }}
        .empty-state {{ color: var(--text-muted); font-size: 13px; padding: 12px; text-align: center; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-title">
            <h1>🏈 {league.settings.name} — Draft Copilot</h1>
            <p>Team: <strong>{my_team.team_name}</strong> (Slot #{my_slot}) | Pick #{next_pick_num} (Round {round_num})</p>
        </div>
        <div class="header-meta">
            <select id="theme-select" class="theme-selector" onchange="setTheme(this.value)">
                <option value="theme-cyberpunk">Cyberpunk Dark (Default)</option>
                <option value="theme-professional">Professional Light</option>
                <option value="theme-y2k">Windows 95/Y2K</option>
            </select>
            {status_badge}
            <span style="font-size: 12px; color: var(--text-muted);">Sync: {now_str}</span>
        </div>
    </div>
    
    <script>
        // Ensure dropdown matches saved theme on load
        document.getElementById('theme-select').value = savedTheme;
    </script>

    <div class="hero-banner">
        <div class="target-card primary" onclick="navigator.clipboard.writeText('{primary}'.split('(')[0].trim());">
            <span class="target-label">🎯 Primary Target (Click to Copy)</span>
            <div class="target-name">{primary}</div>
        </div>
        <div class="target-card backup" onclick="navigator.clipboard.writeText('{backup}'.split('(')[0].trim());">
            <span class="target-label">🔄 Backup Pivot (Click to Copy)</span>
            <div class="target-name">{backup}</div>
        </div>
    </div>

    <div class="main-grid">
        <div>
            <div class="card">
                <div class="card-header">
                    <span>🧠 Tactical Intelligence Engine</span>
                    <span style="color: var(--accent-blue); font-weight: normal;">{model_used}</span>
                </div>
                <div class="card-body">
                    <div class="intel-box">
                        <div class="intel-item news">
                            <div class="intel-title">🌐 Live Google Search Grounding & Injury Wire</div>
                            <div class="intel-body">{news}</div>
                            <div class="search-tags">{search_tags}</div>
                        </div>
                        <div class="intel-item cliff">
                            <div class="intel-title">⚠️ Positional Tier Cliff Warning</div>
                            <div class="intel-body">{cliff}</div>
                        </div>
                        <div class="intel-item threat">
                            <div class="intel-title">🛡️ Opponent Gap Threat ({turn_gap} Picks until Turn)</div>
                            <div class="intel-body">{threat}</div>
                            <div class="radar-stats">
                                <div class="radar-stat-box">
                                    <div class="radar-stat-val">{gap_needs['QB']}</div>
                                    <div class="radar-stat-lbl">QBs Needed</div>
                                </div>
                                <div class="radar-stat-box">
                                    <div class="radar-stat-val">{gap_needs['TE']}</div>
                                    <div class="radar-stat-lbl">TEs Needed</div>
                                </div>
                                <div class="radar-stat-box">
                                    <div class="radar-stat-val">{gap_needs['DST']}</div>
                                    <div class="radar-stat-lbl">D/STs Needed</div>
                                </div>
                            </div>
                        </div>
                        <div class="intel-item rationale">
                            <div class="intel-title">💡 Game-Theory Rationale</div>
                            <div class="intel-body">{rationale}</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span>📋 Top Available Board Slices</span>
                </div>
                <div class="card-body">
                    <div class="board-list">
                        {board_rows}
                    </div>
                </div>
            </div>
        </div>

        <div>
            <div class="card">
                <div class="card-header">
                    <span>🛡️ My Roster ({len(my_team.roster)} Picks)</span>
                </div>
                <div class="card-body">
                    <div class="roster-grid">
                        {roster_rows}
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    with open(HTML_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

def run_draft_watcher():
    print(f"Connecting to ESPN League {LEAGUE_ID}...")
    league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID, fetch_league=True)
    my_team, my_slot = get_my_team_and_slot(league, MY_TEAM_NAME)
    
    print(f"Active Team: {my_team.team_name} (Draft Slot: #{my_slot})")
    print(f"Grounding: Google Search Enabled | Dashboard: {HTML_FILE_PATH}")
    print("Listening to ESPN draft board... (Press Ctrl+C to exit)\n")

    last_pick_count = -1
    last_rec = None
    last_model = "initializing"
    last_queries = []
    last_gap = 0
    last_needs = {"QB": 0, "TE": 0, "DST": 0}
    last_board = []

    while True:
        try:
            league._fetch_league()
            league._fetch_league()
            
            # 🚨 EMERGENCY PATCH: espn-api ignores picks if draft is in-progress (drafted == False)
            draft_data = league.espn_request.league_get(params={'view': 'mDraftDetail'})
            raw_picks = draft_data.get('draftDetail', {}).get('picks', [])
            
            # Filter only picks that have actually been made (playerId is filled)
            made_picks = [p for p in raw_picks if p.get('playerId', 0) > 0]
            
            # Fake the pick objects so the rest of the script works
            class LivePick:
                def __init__(self, p):
                    self.playerName = league.player_map.get(p.get('playerId'), "Unknown Player")
                    self.round_num = p.get('roundId', 1)
            
            current_picks = [LivePick(p) for p in made_picks]
            total_picks = len(current_picks)
            next_pick_number = total_picks + 1
            is_clock, is_deck = is_my_turn_or_on_deck(next_pick_number, my_slot, TOTAL_LEAGUE_TEAMS)

            if total_picks != last_pick_count:
                last_pick_count = total_picks
                recent = [f"{p.playerName} (Rd {p.round_num})" for p in current_picks[-4:]]
                print(f"[Pick #{total_picks}] Next: #{next_pick_number} | Recent: {', '.join(recent) if recent else 'Board opening'}")

                raw_available = league.free_agents(size=60)

                if is_clock or is_deck:
                    status = "🚨 YOU ARE ON THE CLOCK!" if is_clock else "👀 YOU ARE ON DECK (1 PICK AWAY)"
                    print(f"\n{status}")
                    print("Running game-theory audit + Google Search grounding...")

                    rec, model_used, search_queries, turn_gap, gap_needs, structured_board = query_gemini_strategy(
                        league=league,
                        my_team=my_team,
                        current_picks=current_picks,
                        raw_available=raw_available,
                        upcoming_pick_num=next_pick_number,
                        my_slot=my_slot
                    )
                    last_rec, last_model, last_queries, last_gap, last_needs, last_board = rec, model_used, search_queries, turn_gap, gap_needs, structured_board

                    if rec:
                        print(f"🎯 PRIMARY: {rec.primary_target} | 🔄 BACKUP: {rec.backup_target}")
                        if search_queries:
                            print(f"🌐 Searched Web For: {search_queries}")
                        print(f"🩺 Injury/News Status: {rec.verified_news}\n")
                else:
                    _, last_board = slice_available_pool(raw_available)
                    last_gap, last_needs = get_gap_roster_needs(league, next_pick_number, my_slot, TOTAL_LEAGUE_TEAMS)

            render_html_dashboard(
                league=league,
                my_team=my_team,
                my_slot=my_slot,
                next_pick_num=next_pick_number,
                is_clock=is_clock,
                is_deck=is_deck,
                rec=last_rec,
                model_used=last_model,
                search_queries=last_queries,
                turn_gap=last_gap,
                gap_needs=last_needs,
                structured_board=last_board
            )

        except KeyboardInterrupt:
            print("\nExiting Draft Copilot.")
            break
        except Exception as e:
            print(f"[Notice] Polling exception: {e}")

        time.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    run_draft_watcher()

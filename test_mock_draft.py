import os
import sys
import time
import warnings
from espn_api.football import League
from google import genai
from google.genai.errors import ServerError

warnings.filterwarnings("ignore", message=".*automatic function calling.*")

LEAGUE_ID = 384224
YEAR = 2026
ESPN_S2 = "AEC5W1tau4Amz9CZkBDricSPSWos8KWiWeIa8oJQ7MWc6vI8DAZIOqTNMpzo4lDbkQMRMBnY47LTvZCThCoKgudlOTewD6kP3ZnFNjCyiXtSCI9FwyGtTWHlbC%2BXSm0NVwivECmNlnb8%2FI9d5EpVmmJB1EUrhRuMTs8S9dY95EDqqOEA%2BrPFSgll4fJV%2F%2FdPaToHXqVkoF8LbCn5GtxwRtjQL1%2BGe4Jc3Y3RBQREX6In7HSy8yeFZBaHgO4YYeLp9AJMZyW5ZV0FgJK2TJwAEQ5bipyRJONlFuCMUr42Av5GJQ%3D%3D"
SWID = "{F6E8588E-0B1E-4BE5-9056-C26418F284FD}"

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    sys.exit("Error: GEMINI_API_KEY environment variable is not set.")

client = genai.Client(api_key=api_key)

print(f"Connecting to ESPN League {LEAGUE_ID}...")
league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID, fetch_league=True)

settings = league.settings
slot_counts = getattr(settings, "position_slot_counts", {})
scoring_type = getattr(settings, "scoring_type", "PPR / Standard")

print("Pulling current draft pool from ESPN...")
available_pool = league.free_agents(size=25)

MODELS_CASCADE = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]

def generate_with_fallback(prompt):
    """Tries the fastest frontier model; falls back if Google hits a 503 spike."""
    for model_name in MODELS_CASCADE:
        try:
            res = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return res.text.strip(), model_name
        except ServerError as e:
            if "503" in str(e):
                print(f"   [Notice: {model_name} busy (503). Failing over to next model...]")
                time.sleep(0.5)
                continue
            raise e
        except Exception as e:
            # If a model name is unsupported or busy, try next
            print(f"   [Trying next model after: {model_name}]")
            continue
    return "Error: All candidate models temporarily unavailable.", "none"

def run_mock_turn(scenario_title, current_roster, last_picks, pick_num, top_available):
    available_summary = [
        f"- {p.name} ({p.position}, Proj: {getattr(p, 'projected_total_points', 0.0):.1f})"
        for p in top_available[:12]
    ]

    prompt = f"""
You are an elite, mathematically sharp Fantasy Football draft strategist.

LEAGUE ENVIRONMENT:
- Teams: {settings.team_count}
- Roster Slots: {slot_counts}
- Scoring Scheme: {scoring_type}

DRAFT STATE:
- Pick Number: #{pick_num}
- My Current Roster: {", ".join(current_roster) if current_roster else "Empty (Round 1)"}
- Last Picks Off The Board: {", ".join(last_picks) if last_picks else "Draft starting"}

TOP AVAILABLE CANDIDATES:
{chr(10).join(available_summary)}

TASK:
1. Note any immediate positional imperative or run dynamics.
2. Recommend the top 2-3 specific targets from the board right now.
3. For each target, provide a 1-sentence analytical reason (volume, tier cliff, or structural value).

Keep output under 140 words. Be direct and tactical.
"""
    print("\n" + "=" * 32 + f" SCENARIO: {scenario_title} " + "=" * 32)
    print(f"Current Roster: {current_roster}")
    print(f"Recent Picks: {last_picks}")
    print("Querying Gemini with active league settings...")

    advice, used_model = generate_with_fallback(prompt)
    print(f"\n[GEMINI RECOMMENDATION via {used_model}]")
    print(advice)
    print("=" * (66 + len(scenario_title)))

# --- TEST SCENARIO 1: Round 1, Clean Slate ---
run_mock_turn(
    scenario_title="Round 1 (Pick 1.04) - Clean Slate",
    current_roster=[],
    last_picks=["Christian McCaffrey (RB)", "CeeDee Lamb (WR)", "Ja'Marr Chase (WR)"],
    pick_num=4,
    top_available=available_pool
)

# --- TEST SCENARIO 2: Round 3, RB-Heavy Roster Pivot ---
run_mock_turn(
    scenario_title="Round 3 (Pick 3.04) - Testing WR/TE Pivot Need",
    current_roster=["Breece Hall (RB)", "Saquon Barkley (RB)"],
    last_picks=["Nico Collins (WR)", "Sam LaPorta (TE)", "Josh Allen (QB)"],
    pick_num=28,
    top_available=available_pool[8:22]
)

# --- TEST SCENARIO 3: Round 6, Positional Run in Progress ---
run_mock_turn(
    scenario_title="Round 6 (Pick 6.09) - Countering a WR Run",
    current_roster=["Breece Hall (RB)", "Saquon Barkley (RB)", "Jaylen Waddle (WR)", "Amari Cooper (WR)", "Trey McBride (TE)"],
    last_picks=["Deebo Samuel (WR)", "Terry McLaurin (WR)", "George Pickens (WR)", "Calvin Ridley (WR)"],
    pick_num=69,
    top_available=available_pool[12:25]
)

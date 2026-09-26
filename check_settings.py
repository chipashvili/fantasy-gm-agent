import json
from espn_api.football import League

LEAGUE_ID = 384224
YEAR = 2026
ESPN_S2 = "AEC5W1tau4Amz9CZkBDricSPSWos8KWiWeIa8oJQ7MWc6vI8DAZIOqTNMpzo4lDbkQMRMBnY47LTvZCThCoKgudlOTewD6kP3ZnFNjCyiXtSCI9FwyGtTWHlbC%2BXSm0NVwivECmNlnb8%2FI9d5EpVmmJB1EUrhRuMTs8S9dY95EDqqOEA%2BrPFSgll4fJV%2F%2FdPaToHXqVkoF8LbCn5GtxwRtjQL1%2BGe4Jc3Y3RBQREX6In7HSy8yeFZBaHgO4YYeLp9AJMZyW5ZV0FgJK2TJwAEQ5bipyRJONlFuCMUr42Av5GJQ%3D%3D"
SWID = "{F6E8588E-0B1E-4BE5-9056-C26418F284FD}"

print(f"Fetching settings for League {LEAGUE_ID}...")
league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID, fetch_league=True)

settings = league.settings
print("\n" + "=" * 30 + " LEAGUE SETTINGS AUDIT " + "=" * 30)

# 1. High-level parsed settings
settings_dict = vars(settings)
for key, value in sorted(settings_dict.items()):
    if not key.startswith("_"):
        print(f"• {key}: {value}")

# 2. Check roster configuration specifically
print("\n" + "=" * 30 + " STARTING ROSTER SLOTS " + "=" * 30)
if hasattr(settings, "position_slot_counts"):
    for slot, count in settings.position_slot_counts.items():
        if count > 0:
            print(f"• {slot}: {count}")
elif hasattr(settings, "roster_slots"):
    for slot, count in settings.roster_slots.items():
        if count > 0:
            print(f"• {slot}: {count}")

# 3. Check scoring items / rules
print("\n" + "=" * 30 + " SCORING FORMAT / RULES " + "=" * 30)
if hasattr(settings, "scoring_type"):
    print(f"Scoring Type: {settings.scoring_type}")
if hasattr(settings, "scoring_items"):
    print(f"Custom Scoring Items Count: {len(settings.scoring_items)}")
    # Sample common scoring rules (e.g. reception points)
    for item in settings.scoring_items[:10]:
        print(f"  - {item}")
print("=" * 83)

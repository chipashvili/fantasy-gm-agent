import os
from espn_api.football import League
from google import genai

LEAGUE_ID = 384224
YEAR = 2026
ESPN_S2 = "AEC5W1tau4Amz9CZkBDricSPSWos8KWiWeIa8oJQ7MWc6vI8DAZIOqTNMpzo4lDbkQMRMBnY47LTvZCThCoKgudlOTewD6kP3ZnFNjCyiXtSCI9FwyGtTWHlbC%2BXSm0NVwivECmNlnb8%2FI9d5EpVmmJB1EUrhRuMTs8S9dY95EDqqOEA%2BrPFSgll4fJV%2F%2FdPaToHXqVkoF8LbCn5GtxwRtjQL1%2BGe4Jc3Y3RBQREX6In7HSy8yeFZBaHgO4YYeLp9AJMZyW5ZV0FgJK2TJwAEQ5bipyRJONlFuCMUr42Av5GJQ%3D%3D"
SWID = "{F6E8588E-0B1E-4BE5-9056-C26418F284FD}"

print("1. Testing ESPN connection...")
try:
    league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)
    print(f"   Success! Connected to league: {league.settings.name}")
    print(f"   Teams found: {[t.team_name for t in league.teams]}")
except Exception as e:
    print(f"   ESPN connection failed: {e}")

print("\n2. Testing Gemini API...")
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("   GEMINI_API_KEY environment variable is not set!")
    else:
        client = genai.Client(api_key=api_key)
        res = client.models.generate_content(
            model="gemini-3.6-flash",
            contents="Say 'Gemini is online and ready for fantasy draft!'"
        )
        print(f"   Success! Response: {res.text.strip()}")
except Exception as e:
    print(f"   Gemini connection failed: {e}")

import os
import json
from collections import Counter
from espn_api.football import League
from google import genai
from google.genai import types
from memory_manager import MemoryManager

LEAGUE_ID = 384224
YEAR = 2026
ESPN_S2 = "AEC5W1tau4Amz9CZkBDricSPSWos8KWiWeIa8oJQ7MWc6vI8DAZIOqTNMpzo4lDbkQMRMBnY47LTvZCThCoKgudlOTewD6kP3ZnFNjCyiXtSCI9FwyGtTWHlbC%2BXSm0NVwivECmNlnb8%2FI9d5EpVmmJB1EUrhRuMTs8S9dY95EDqqOEA%2BrPFSgll4fJV%2F%2FdPaToHXqVkoF8LbCn5GtxwRtjQL1%2BGe4Jc3Y3RBQREX6In7HSy8yeFZBaHgO4YYeLp9AJMZyW5ZV0FgJK2TJwAEQ5bipyRJONlFuCMUr42Av5GJQ%3D%3D"
SWID = "{F6E8588E-0B1E-4BE5-9056-C26418F284FD}"

class TradeAnalyzer:
    def __init__(self):
        self.my_team_name = "Ivy league douche"
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
        self.league = None
        self.memory = MemoryManager()

    def refresh(self):
        s2 = os.environ.get("ESPN_S2", ESPN_S2)
        swid = os.environ.get("SWID", SWID)
        league_id = int(os.environ.get("ESPN_LEAGUE_ID", LEAGUE_ID))
        year = int(os.environ.get("ESPN_YEAR", YEAR))
        self.league = League(league_id=league_id, year=year, espn_s2=s2, swid=swid)

    def scan_for_trades(self):
        self.refresh()
        my_team = next((t for t in self.league.teams if t.team_name == self.my_team_name), self.league.teams[0])
        other_teams = [t for t in self.league.teams if t.team_id != my_team.team_id]
        
        my_roster = [{"id": p.playerId, "name": p.name, "pos": p.position, "proj": p.projected_total_points} for p in my_team.roster]
        
        proposals = []
        memory_context = self.memory.get_memory_context()
        
        # We look for simple imbalances for now, or just let Gemini find them
        if not self.client:
            return []

        # Sample a few other teams to avoid massive prompt token limits
        for opponent in other_teams[:3]:
            opp_roster = [{"id": p.playerId, "name": p.name, "pos": p.position, "proj": p.projected_total_points} for p in opponent.roster]
            
            prompt = f"""
            You are "The Commish", a highly aggressive, sarcastic, yet mathematically brilliant Fantasy Football AI Agent.
            Your job is to find a mutually beneficial 1-for-1 or 2-for-2 trade between MY TEAM and the OPPONENT.
            Target "Buy Low" candidates on the opponent's team if possible.
            
            MEMORY OF PAST DECISIONS (CRITICAL):
            {memory_context}
            DO NOT SUGGEST TRADES THAT THE USER PREVIOUSLY REJECTED. Learn from what they reject.
            
            MY TEAM:
            {json.dumps(my_roster, indent=2)}
            
            OPPONENT TEAM ({opponent.team_name}):
            {json.dumps(opp_roster, indent=2)}
            
            Output ONLY a valid JSON object matching these keys. Ensure you include the player IDs exactly as provided.
            {{
                "give": [{{"id": 123, "name": "Player A"}}],
                "get": [{{"id": 456, "name": "Player B"}}],
                "rationale": "Sarcastic, trash-talking explanation of why this trade makes sense and why the opponent is dumb enough to accept it."
            }}
            If no good trade exists, output an empty JSON object: {{}}
            """
            try:
                res = self.client.models.generate_content(
                    model="gemini-3.7-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.2)
                )
                text = res.text.strip().strip("```json").strip("```").strip()
                data = json.loads(text)
                if data and "give" in data and "get" in data:
                    data["opponent"] = opponent.team_name
                    data["opponent_id"] = opponent.team_id
                    data["my_team_id"] = my_team.team_id
                    proposals.append(data)
            except Exception as e:
                print(f"Trade analysis failed for {opponent.team_name}: {e}")
                
        return proposals

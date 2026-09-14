import os
import json
from collections import Counter
from espn_api.football import League
from memory_manager import MemoryManager
from llm_client import generate_completion


class TradeAnalyzer:
    def __init__(self):
        self.my_team_name = os.environ.get("ESPN_TEAM_NAME", "Team Name")
        
        self.league = None
        self.memory = MemoryManager()

    def refresh(self):
        s2 = os.environ.get("ESPN_S2")
        swid = os.environ.get("SWID")
        league_id = int(os.environ.get("ESPN_LEAGUE_ID", 0))
        year = int(os.environ.get("ESPN_YEAR", 2026))
        self.league = League(league_id=league_id, year=year, espn_s2=s2, swid=swid)

    def scan_for_trades(self):
        self.refresh()
        my_team = next((t for t in self.league.teams if t.team_name == self.my_team_name), self.league.teams[0])
        other_teams = [t for t in self.league.teams if t.team_id != my_team.team_id]
        
        my_roster = [{"id": p.playerId, "name": p.name, "pos": p.position, "proj": p.projected_total_points} for p in my_team.roster]
        
        proposals = []
        memory_context = self.memory.get_memory_context()
        
        # We look for simple imbalances for now, or just let Gemini find them
        

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
                text = generate_completion(prompt)
                data = json.loads(text)
                if data and "give" in data and "get" in data:
                    data["opponent"] = opponent.team_name
                    data["opponent_id"] = opponent.team_id
                    data["my_team_id"] = my_team.team_id
                    proposals.append(data)
            except Exception as e:
                print(f"Trade analysis failed for {opponent.team_name}: {e}")
                
        return proposals

import os
import json
from espn_api.football import League
from google import genai
from google.genai import types
from memory_manager import MemoryManager

LEAGUE_ID = 384224
YEAR = 2026
ESPN_S2 = "AEC5W1tau4Amz9CZkBDricSPSWos8KWiWeIa8oJQ7MWc6vI8DAZIOqTNMpzo4lDbkQMRMBnY47LTvZCThCoKgudlOTewD6kP3ZnFNjCyiXtSCI9FwyGtTWHlbC%2BXSm0NVwivECmNlnb8%2FI9d5EpVmmJB1EUrhRuMTs8S9dY95EDqqOEA%2BrPFSgll4fJV%2F%2FdPaToHXqVkoF8LbCn5GtxwRtjQL1%2BGe4Jc3Y3RBQREX6In7HSy8yeFZBaHgO4YYeLp9AJMZyW5ZV0FgJK2TJwAEQ5bipyRJONlFuCMUr42Av5GJQ%3D%3D"
SWID = "{F6E8588E-0B1E-4BE5-9056-C26418F284FD}"

class WaiverScout:
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

    def scan_waivers(self):
        self.refresh()
        if not self.client:
            return []

        my_team = next((t for t in self.league.teams if t.team_name == self.my_team_name), self.league.teams[0])
        bench = [p for p in my_team.roster if p.lineupSlot in ['BE', 'IR']]
        
        bench_data = [{"id": p.playerId, "name": p.name, "pos": p.position, "proj": p.projected_total_points, "status": p.injuryStatus} for p in bench]
        
        # Get top 30 free agents
        fas = self.league.free_agents(size=30)
        fa_data = [{"id": p.playerId, "name": p.name, "pos": p.position, "proj": p.projected_total_points, "status": p.injuryStatus} for p in fas]

        memory_context = self.memory.get_memory_context()

        prompt = f"""
        You are "The Commish", a highly aggressive, sarcastic, yet mathematically brilliant Fantasy Football AI Agent.
        Your job is to scout the waiver wire (Free Agents) and find the single best ADD/DROP move for my team.
        You should drop the weakest bench player (lowest projected or injured) for the best available free agent.
        
        MEMORY OF PAST DECISIONS (CRITICAL):
        {memory_context}
        DO NOT SUGGEST MOVES THAT THE USER PREVIOUSLY REJECTED.

        MY BENCH:
        {json.dumps(bench_data, indent=2)}
        
        TOP AVAILABLE FREE AGENTS:
        {json.dumps(fa_data, indent=2)}
        
        Output ONLY a valid JSON object matching these keys. Ensure you include the player IDs exactly as provided.
        {{
            "add": {{"id": 123, "name": "Player A"}},
            "drop": {{"id": 456, "name": "Player B"}},
            "rationale": "Sarcastic, trash-talking explanation of why my bench player is garbage and why I need this free agent."
        }}
        If no good moves exist, output an empty JSON object: {{}}
        """
        
        try:
            res = self.client.models.generate_content(
                model="gemini-3.7-flash",
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2)
            )
            text = res.text.strip().strip("```json").strip("```").strip()
            data = json.loads(text)
            if data and "add" in data and "drop" in data:
                data["team_id"] = my_team.team_id
                data["current_week"] = self.league.current_week
                return [data]
        except Exception as e:
            print(f"Waiver analysis failed: {e}")
            
        return []

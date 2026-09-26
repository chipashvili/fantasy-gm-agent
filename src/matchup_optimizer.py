import os
from espn_api.football import League

LEAGUE_ID = 384224
YEAR = 2026
ESPN_S2 = "AEC5W1tau4Amz9CZkBDricSPSWos8KWiWeIa8oJQ7MWc6vI8DAZIOqTNMpzo4lDbkQMRMBnY47LTvZCThCoKgudlOTewD6kP3ZnFNjCyiXtSCI9FwyGtTWHlbC%2BXSm0NVwivECmNlnb8%2FI9d5EpVmmJB1EUrhRuMTs8S9dY95EDqqOEA%2BrPFSgll4fJV%2F%2FdPaToHXqVkoF8LbCn5GtxwRtjQL1%2BGe4Jc3Y3RBQREX6In7HSy8yeFZBaHgO4YYeLp9AJMZyW5ZV0FgJK2TJwAEQ5bipyRJONlFuCMUr42Av5GJQ%3D%3D"
SWID = "{F6E8588E-0B1E-4BE5-9056-C26418F284FD}"

class MatchupOptimizer:
    def __init__(self):
        self.my_team_name = "Ivy league douche"
        self.league = None

    def refresh(self):
        s2 = os.environ.get("ESPN_S2", ESPN_S2)
        swid = os.environ.get("SWID", SWID)
        league_id = int(os.environ.get("ESPN_LEAGUE_ID", LEAGUE_ID))
        year = int(os.environ.get("ESPN_YEAR", YEAR))
        self.league = League(league_id=league_id, year=year, espn_s2=s2, swid=swid)

    def _get_player_projection(self, player):
        wk = getattr(self.league, 'current_week', None)
        stats = getattr(player, 'stats', {})
        if isinstance(stats, dict) and wk in stats:
            proj = stats[wk].get('projected_points')
            if proj is not None:
                return float(proj)
        return float(getattr(player, 'projected_avg_points', 0) or getattr(player, 'projected_total_points', 0) or 0.0)

    def analyze_start_sit(self):
        self.refresh()
        my_team = next((t for t in self.league.teams if t.team_name == self.my_team_name), self.league.teams[0])
        
        starters = [p for p in my_team.roster if p.lineupSlot not in ['BE', 'IR']]
        bench = [p for p in my_team.roster if p.lineupSlot == 'BE']
        
        warnings = []
        current_week = self.league.current_week
        
        # 1. Check for Bye or IR/OUT/DOUBTFUL/SUSP warnings
        for p in starters:
            status = getattr(p, 'injuryStatus', 'ACTIVE')
            is_bye = str(current_week) not in getattr(p, 'schedule', {})
            
            if status in ['OUT', 'IR', 'DOUBTFUL', 'SUSP']:
                warnings.append(f"⚠️ {p.name} is starting but is marked {status}.")
            if is_bye:
                warnings.append(f"⚠️ {p.name} is starting but is on BYE.")

        # 2. Start/Sit recommendations based on weekly matchup projections
        best_rec_per_starter = {}
        
        for b_player in bench:
            # Skip injured bench players
            if getattr(b_player, 'injuryStatus', 'ACTIVE') in ['OUT', 'IR', 'SUSP']:
                continue
                
            b_proj = self._get_player_projection(b_player)
            
            for s_player in starters:
                # Check if bench player is eligible for the starter's current lineup slot
                if s_player.lineupSlot in b_player.eligibleSlots:
                    s_proj = self._get_player_projection(s_player)
                    diff = b_proj - s_proj
                    if diff > 3.0:
                        existing = best_rec_per_starter.get(s_player.playerId)
                        if not existing or diff > existing['diff']:
                            best_rec_per_starter[s_player.playerId] = {
                                'diff': diff,
                                'sit': s_player,
                                'start': b_player,
                                'reason': f"{b_player.name} is projected {b_proj:.1f} pts vs {s_player.name}'s {s_proj:.1f} pts this week."
                            }
        
        recommendations = [{k: v for k, v in rec.items() if k != 'diff'} for rec in best_rec_per_starter.values()]
        return warnings, recommendations, my_team.team_id

import os
from espn_api.football import League


class MatchupOptimizer:
    def __init__(self):
        self.my_team_name = os.environ.get("ESPN_TEAM_NAME", "Team Name")
        self.league = None

    def refresh(self):
        s2 = os.environ.get("ESPN_S2")
        swid = os.environ.get("SWID")
        league_id = int(os.environ.get("ESPN_LEAGUE_ID", 0))
        year = int(os.environ.get("ESPN_YEAR", 2026))
        self.league = League(league_id=league_id, year=year, espn_s2=s2, swid=swid)

    def analyze_start_sit(self):
        self.refresh()
        my_team = next((t for t in self.league.teams if t.team_name == self.my_team_name), self.league.teams[0])
        
        starters = [p for p in my_team.roster if p.lineupSlot not in ['BE', 'IR']]
        bench = [p for p in my_team.roster if p.lineupSlot == 'BE']
        
        warnings = []
        recommendations = []
        
        # 1. Check for Bye or IR/OUT warnings
        for p in starters:
            status = getattr(p, 'injuryStatus', 'ACTIVE')
            bye = getattr(p, 'on_bye_week', 0) # Just simulating bye check; depends on week
            
            if status in ['OUT', 'IR']:
                warnings.append(f"⚠️ {p.name} is starting but is marked {status}.")
            if bye == True: # If they are on bye this week
                warnings.append(f"⚠️ {p.name} is starting but is on BYE.")

        # 2. Simple Start/Sit recommendations based strictly on drafted bench
        # We compare bench players against starters in the same slot if projected points are significantly higher (+3 pts)
        best_recs_by_bench_player = {}
        
        for b_player in bench:
            b_proj = getattr(b_player, 'projected_total_points', 0)
            
            best_diff = 0
            best_rec = None
            
            for s_player in starters:
                # Check if eligible to swap
                if b_player.position in s_player.eligibleSlots:
                    s_proj = getattr(s_player, 'projected_total_points', 0)
                    diff = b_proj - s_proj
                    if diff > 3.0 and diff > best_diff:
                        best_diff = diff
                        best_rec = {
                            'sit': s_player,
                            'start': b_player,
                            'reason': f"{b_player.name} is projected {b_proj:.1f} pts vs {s_player.name}'s {s_proj:.1f} pts."
                        }
            
            if best_rec:
                recommendations.append(best_rec)
                        
        return warnings, recommendations, my_team.team_id

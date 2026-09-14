import os
from espn_api.football import League


class LineupOptimizer:
    def __init__(self):
        self.league = League(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)
        # Find our team, assume we are 'Ivy league douche' for now or the first team
        self.my_team = None
        for t in self.league.teams:
            if t.team_name == "Ivy league douche":
                self.my_team = t
                break
        if not self.my_team:
            self.my_team = self.league.teams[0]

    def refresh(self):
        self.league._fetch_league()

    def check_lineup_emergencies(self):
        """
        Checks the starting lineup for players marked OUT or IR.
        Returns a list of emergency swaps needed.
        """
        self.refresh()
        emergencies = []
        
        # In a real scenario, we'd check if the game is within 60 minutes.
        # For this logic, we just look at the lineup.
        for player in self.my_team.roster:
            if player.lineupSlot not in ['BE', 'IR']:
                status = getattr(player, 'injuryStatus', 'ACTIVE')
                if status in ['OUT', 'IR']:
                    emergencies.append(player)
        
        return emergencies

    def execute_emergency_swap(self, injured_player):
        """
        Finds the highest projected bench player to swap in.
        """
        best_bench = None
        best_proj = -1
        
        for p in self.my_team.roster:
            if p.lineupSlot == 'BE' and p.position in injured_player.eligibleSlots:
                proj = getattr(p, 'projected_total_points', 0)
                if proj > best_proj:
                    best_proj = proj
                    best_bench = p
                    
        if best_bench:
            print(f"[ACTION] Swapping {injured_player.name} (OUT) for {best_bench.name} (Proj {best_proj})")
            # In a real scenario with full API support:
            # self.league.espn_request.post(...)
            return True, best_bench
        return False, None

    def evaluate_waiver_claims(self):
        """
        Scans free agents and compares to our worst bench player.
        """
        self.refresh()
        free_agents = self.league.free_agents(size=10)
        
        # Find our worst bench player
        worst_bench = None
        worst_proj = 999
        for p in self.my_team.roster:
            if p.lineupSlot == 'BE':
                proj = getattr(p, 'projected_total_points', 0)
                if proj < worst_proj:
                    worst_proj = proj
                    worst_bench = p
                    
        recommendations = []
        for fa in free_agents:
            fa_proj = getattr(fa, 'projected_total_points', 0)
            if fa_proj > (worst_proj + 15):  # Arbitrary 15 point projected improvement over season
                recommendations.append({
                    'drop': worst_bench,
                    'add': fa,
                    'reason': f"Proj +{fa_proj - worst_proj:.1f} pts"
                })
        
        return recommendations

import os
import requests
import json

class ESPNExecutor:
    def __init__(self, league_id, year, espn_s2, swid):
        self.league_id = league_id
        self.year = year
        self.initial_s2 = espn_s2
        self.initial_swid = swid
        self.base_url = f"https://lm-api-writes.fantasy.espn.com/apis/v3/games/ffl/seasons/{year}/segments/0/leagues/{league_id}"

    def _get_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Origin": "https://fantasy.espn.com",
            "x-fantasy-source": "kona"
        }

    def _get_cookies(self):
        return {
            "espn_s2": os.environ.get("ESPN_S2", self.initial_s2),
            "swid": os.environ.get("SWID", self.initial_swid)
        }

    def propose_trade(self, from_team_id, to_team_id, give_player_ids, get_player_ids):
        """
        Submits a trade proposal to the ESPN API.
        """
        endpoint = f"{self.base_url}/transactions/"
        
        items = []
        for pid in give_player_ids:
            items.append({
                "fromTeamId": from_team_id,
                "toTeamId": to_team_id,
                "playerId": pid,
                "type": "TRADE"
            })
            
        for pid in get_player_ids:
            items.append({
                "fromTeamId": to_team_id,
                "toTeamId": from_team_id,
                "playerId": pid,
                "type": "TRADE"
            })

        payload = {
            "executionType": "EXECUTE",
            "isLeagueManager": False,
            "items": items,
            "type": "PROPOSAL"
        }

        try:
            res = requests.post(endpoint, json=payload, cookies=self._get_cookies(), headers=self._get_headers())
            if res.status_code in [200, 201, 202]:
                return True, "Trade proposal submitted successfully."
            else:
                return False, f"API Error: {res.status_code} - {res.text}"
        except Exception as e:
            return False, f"Request Exception: {str(e)}"

    def swap_lineup(self, team_id, benched_player_id, started_player_id, from_slot_id, to_slot_id=20, scoring_period=1):
        endpoint = f"{self.base_url}/transactions/"
        
        payload = {
            "executionType": "EXECUTE",
            "isLeagueManager": False,
            "teamId": team_id,
            "scoringPeriodId": scoring_period,
            "items": [
                {
                    "playerId": benched_player_id, # This is the player currently on the bench
                    "type": "LINEUP",
                    "fromLineupSlotId": to_slot_id, # Bench (20)
                    "toLineupSlotId": from_slot_id # Target Slot
                },
                {
                    "playerId": started_player_id, # This is the player currently starting
                    "type": "LINEUP",
                    "fromLineupSlotId": from_slot_id, # Target Slot
                    "toLineupSlotId": to_slot_id # Bench (20)
                }
            ],
            "type": "ROSTER"
        }
        
        try:
            res = requests.post(endpoint, json=payload, cookies=self._get_cookies(), headers=self._get_headers())
            if res.status_code in [200, 201, 202]:
                return True, "Lineup swap executed successfully."
            else:
                return False, f"API Error: {res.status_code} - {res.text}"
        except Exception as e:
            return False, f"Request Exception: {str(e)}"

    def claim_waiver(self, team_id, add_player_id, drop_player_id, scoring_period=1):
        endpoint = f"{self.base_url}/transactions/"
        
        payload = {
            "executionType": "EXECUTE",
            "isLeagueManager": False,
            "teamId": team_id,
            "scoringPeriodId": scoring_period,
            "items": [
                {
                    "playerId": add_player_id,
                    "type": "ADD",
                    "toTeamId": team_id
                },
                {
                    "playerId": drop_player_id,
                    "type": "DROP",
                    "fromTeamId": team_id
                }
            ],
            "type": "WAIVER"
        }

        try:
            res = requests.post(endpoint, json=payload, cookies=self._get_cookies(), headers=self._get_headers())
            return res.status_code in [200, 201, 202], f"Status: {res.status_code}, Body: {res.text}"
        except Exception as e:
            return False, f"Request Exception: {str(e)}"

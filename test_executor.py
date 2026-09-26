import sys
import os
import requests

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from espn_executor import ESPNExecutor

LEAGUE_ID = 384224
YEAR = 2026
ESPN_S2 = "AEC5W1tau4Amz9CZkBDricSPSWos8KWiWeIa8oJQ7MWc6vI8DAZIOqTNMpzo4lDbkQMRMBnY47LTvZCThCoKgudlOTewD6kP3ZnFNjCyiXtSCI9FwyGtTWHlbC%2BXSm0NVwivECmNlnb8%2FI9d5EpVmmJB1EUrhRuMTs8S9dY95EDqqOEA%2BrPFSgll4fJV%2F%2FdPaToHXqVkoF8LbCn5GtxwRtjQL1%2BGe4Jc3Y3RBQREX6In7HSy8yeFZBaHgO4YYeLp9AJMZyW5ZV0FgJK2TJwAEQ5bipyRJONlFuCMUr42Av5GJQ%3D%3D"
SWID = "{F6E8588E-0B1E-4BE5-9056-C26418F284FD}"

executor = ESPNExecutor(league_id=LEAGUE_ID, year=YEAR, espn_s2=ESPN_S2, swid=SWID)

print("Testing ESPN Executor Write Access (Dummy Trade)...")
success, response_msg = executor.propose_trade(from_team_id=1, to_team_id=2, give_player_ids=[-1], get_player_ids=[-2])
print(f"Result: {response_msg}")

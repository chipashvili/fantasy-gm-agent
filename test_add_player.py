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

endpoint = f"{executor.base_url}/transactions/"

# Pure ADD for Patrick Mahomes (3139477)
payload = {
    "executionType": "EXECUTE",
    "isLeagueManager": False,
    "items": [
        {
            "playerId": 3139477,
            "type": "ADD",
            "toTeamId": 3
        }
    ],
    "type": "WAIVER"
}

res = requests.post(endpoint, json=payload, cookies=executor._get_cookies(), headers=executor._get_headers())
print("Result:", res.status_code, res.text)

import os
import requests

LEAGUE_ID = 384224
YEAR = 2026
ESPN_S2 = "AEAMUoQ0u%2Bh7Azcf1JKyaYwEQI8msCseb4fjaZNEqXpf1eLJTwXWzRXlumShCFzpBsRU%2FysrXqYW%2Fm0RZ%2FNB%2FaGTL6NsL9vZh%2BxdaLnYV7XPWeqbYylXPD9ELF8a9gkZUcgVrgTw1kmk3M4fjfydxe%2FVj3qaksJBF8eEChg0iaqUK%2FK%2BOd%2FuvBen7c3csE5zCJhvrIHmdQfLwGZArvsTEPQKW072x7MdSijTG92CCeMv%2BI1vXg59fIpgfVA6O7uVroGCEGkEa4UznxeoLqA3kmkUJLdgX%2BBYOX6g2iSofF0S0A%3D%3D"
SWID = "{F6E8588E-0B1E-4BE5-9056-C26418F284FD}"

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Origin": "https://fantasy.espn.com",
    "x-fantasy-platform": "espn-fantasy-web",
    "x-fantasy-source": "kona"
}
cookies = {
    "espn_s2": ESPN_S2,
    "swid": SWID
}

write_url = f"https://lm-api-writes.fantasy.espn.com/apis/v3/games/ffl/seasons/{YEAR}/segments/0/leagues/{LEAGUE_ID}/teams/3"

payload = {
    "abbrev": "BOT"
}

res = requests.post(
    write_url,
    json=payload,
    headers=headers,
    cookies=cookies
)

print("Status:", res.status_code)
print("Response:", res.text)

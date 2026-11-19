import json, os, urllib.request, urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

API_KEY=os.environ.get("API_FOOTBALL_KEY")
if not API_KEY:
    raise SystemExit("Missing API_FOOTBALL_KEY repository secret")
today=datetime.now(ZoneInfo("Africa/Kampala")).date().isoformat()
url=f"https://v3.football.api-sports.io/fixtures?date={today}&timezone=Africa%2FKampala"
req=urllib.request.Request(url,headers={"x-apisports-key":API_KEY,"Accept":"application/json"})
try:
    with urllib.request.urlopen(req,timeout=30) as response:
        payload=json.loads(response.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    detail=e.read().decode("utf-8","replace")
    raise SystemExit(f"API-Football HTTP {e.code}: {detail[:1000]}")
errors=payload.get("errors")
if errors:
    raise SystemExit(f"API-Football returned errors: {errors}")
fixtures=[]
for item in payload.get("response",[]):
    fx=item.get("fixture",{}); teams=item.get("teams",{}); goals=item.get("goals",{})
    league=item.get("league",{}); status=fx.get("status",{})
    fixtures.append({
      "id":fx.get("id"),"date":fx.get("date"),"timestamp":fx.get("timestamp"),
      "status":status.get("long"),"shortStatus":status.get("short"),
      "home":(teams.get("home") or {}).get("name"),"away":(teams.get("away") or {}).get("name"),
      "homeLogo":(teams.get("home") or {}).get("logo"),"awayLogo":(teams.get("away") or {}).get("logo"),
      "homeGoals":goals.get("home"),"awayGoals":goals.get("away"),
      "league":league.get("name"),"country":league.get("country"),"leagueLogo":league.get("logo"),
      "round":league.get("round"),"venue":(fx.get("venue") or {}).get("name")
    })
out={"date":today,"timezone":"Africa/Kampala","provider":"API-Football","fetchedAt":datetime.now(ZoneInfo("Africa/Kampala")).isoformat(),"fixtureCount":len(fixtures),"fixtures":fixtures}
Path("docs/data").mkdir(parents=True,exist_ok=True)
Path("docs/data/fixtures.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"Saved {len(fixtures)} fixtures for {today}")

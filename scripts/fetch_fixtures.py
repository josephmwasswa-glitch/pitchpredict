import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# SportScore offers a no-key public fixtures endpoint. Its free tier requires
# a visible attribution link on the website (added in docs/index.html).
today = datetime.now(ZoneInfo("Africa/Kampala")).date().isoformat()
url = f"https://sportscore.com/api/v1/fixtures/?sport=football&date={today}&limit=200"
req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "ConCSoccer/1.0"})
try:
    with urllib.request.urlopen(req, timeout=35) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception as exc:
    raise SystemExit(f"SportScore fixture request failed: {exc}")

def first(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        value = obj.get(key)
        if value is not None and value != "":
            return value
    return None

def name(value):
    if isinstance(value, dict):
        return first(value, "name", "title", "display_name", "short_name")
    return value

items = payload if isinstance(payload, list) else first(payload, "matches", "fixtures", "data", "results")
if isinstance(items, dict):
    items = first(items, "matches", "fixtures", "data", "results")
if not isinstance(items, list):
    raise SystemExit(f"Unexpected SportScore response shape. Top-level keys: {list(payload) if isinstance(payload, dict) else type(payload).__name__}")

fixtures = []
for item in items:
    if not isinstance(item, dict):
        continue
    home = name(first(item, "home", "home_team", "homeTeam", "team_home"))
    away = name(first(item, "away", "away_team", "awayTeam", "team_away"))
    if not home or not away:
        teams = item.get("teams") or {}
        home = home or name(first(teams, "home", "local"))
        away = away or name(first(teams, "away", "visitor"))
    if not home or not away:
        continue
    score = item.get("score") or {}
    if isinstance(score, dict):
        hg = first(item, "home_score", "homeGoals", "goals_home")
        ag = first(item, "away_score", "awayGoals", "goals_away")
        hg = hg if hg is not None else first(score, "home", "home_score", "homeGoals")
        ag = ag if ag is not None else first(score, "away", "away_score", "awayGoals")
    else:
        hg = ag = None
    competition = item.get("competition") or item.get("league") or {}
    country = item.get("country")
    if isinstance(competition, dict):
        league_name = first(competition, "name", "title", "short_name")
        country = country or name(first(competition, "country", "area"))
    else:
        league_name = competition
    kickoff = first(item, "date", "kickoff", "kickoff_time", "start_time", "utc_date", "time")
    status = first(item, "status", "state", "match_status") or "Scheduled"
    if isinstance(status, dict):
        status = first(status, "name", "long", "short") or "Scheduled"
    fixtures.append({
        "id": first(item, "id", "match_id", "fixture_id", "slug"),
        "date": kickoff,
        "status": status,
        "shortStatus": first(item, "status_short", "short_status"),
        "home": home,
        "away": away,
        "homeLogo": first(item, "home_logo", "homeLogo"),
        "awayLogo": first(item, "away_logo", "awayLogo"),
        "homeGoals": hg,
        "awayGoals": ag,
        "league": league_name or "Competition not supplied",
        "country": country or "",
        "leagueLogo": first(item, "league_logo", "competition_logo"),
        "round": first(item, "round", "matchday"),
        "venue": first(item, "venue", "stadium")
    })

if items and not fixtures:
    raise SystemExit("SportScore returned records, but no recognizable home/away team fields were found. No data was published.")

out = {
    "date": today,
    "timezone": "Africa/Kampala",
    "provider": "SportScore",
    "fetchedAt": datetime.now(ZoneInfo("Africa/Kampala")).isoformat(),
    "fixtureCount": len(fixtures),
    "fixtures": fixtures
}
Path("docs/data").mkdir(parents=True, exist_ok=True)
Path("docs/data/fixtures.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved {len(fixtures)} real fixtures for {today} from SportScore")

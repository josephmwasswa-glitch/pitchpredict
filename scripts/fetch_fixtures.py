import json
import urllib.request
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

# ConC Soccer's football day runs 06:00 EAT through 05:59:59 EAT next day.
TZ = ZoneInfo("Africa/Kampala")
now = datetime.now(TZ)
start_date = now.date() if now.time() >= time(6, 0) else (now.date() - timedelta(days=1))
window_start = datetime.combine(start_date, time(6, 0), TZ)
window_end = window_start + timedelta(days=1)
query_dates = [start_date, start_date + timedelta(days=1)]

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

def unpack(payload):
    items = payload if isinstance(payload, list) else first(payload, "matches", "fixtures", "data", "results")
    if isinstance(items, dict):
        items = first(items, "matches", "fixtures", "data", "results")
    if not isinstance(items, list):
        raise ValueError(f"Unexpected SportScore response shape: {type(payload).__name__}")
    return items

fixtures_by_key = {}
for query_date in query_dates:
    url = f"https://sportscore.com/api/v1/fixtures/?sport=football&date={query_date.isoformat()}&limit=200"
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "ConCSoccer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise SystemExit(f"SportScore fixture request failed for {query_date}: {exc}")

    for item in unpack(payload):
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
        kickoff = first(item, "date", "kickoff", "kickoff_time", "start_time", "utc_date", "time")
        if not kickoff:
            continue
        try:
            kickoff_dt = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
            if kickoff_dt.tzinfo is None:
                kickoff_dt = kickoff_dt.replace(tzinfo=timezone.utc)
            kickoff_local = kickoff_dt.astimezone(TZ)
        except (ValueError, TypeError):
            continue
        if not (window_start <= kickoff_local < window_end):
            continue

        score = item.get("score") or {}
        hg = first(item, "home_score", "homeGoals", "goals_home")
        ag = first(item, "away_score", "awayGoals", "goals_away")
        if isinstance(score, dict):
            hg = hg if hg is not None else first(score, "home", "home_score", "homeGoals")
            ag = ag if ag is not None else first(score, "away", "away_score", "awayGoals")
        competition = item.get("competition") or item.get("league") or {}
        country = item.get("country")
        if isinstance(competition, dict):
            league_name = first(competition, "name", "title", "short_name")
            country = country or name(first(competition, "country", "area"))
        else:
            league_name = competition
        fixture = {
            "id": first(item, "id", "match_id", "fixture_id", "slug"),
            "date": kickoff_dt.isoformat(),
            "status": first(item, "status", "state", "match_status") or "Scheduled",
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
        }
        key = str(fixture["id"] or "") or f"{kickoff_dt.isoformat()}|{home}|{away}"
        fixtures_by_key[key] = fixture

fixtures = sorted(fixtures_by_key.values(), key=lambda x: x["date"])
out = {
    "date": start_date.isoformat(),
    "timezone": "Africa/Kampala",
    "dayWindow": {
        "startsAt": window_start.isoformat(),
        "endsBefore": window_end.isoformat(),
        "label": "06:00 EAT to 05:59 EAT next day"
    },
    "provider": "SportScore",
    "fetchedAt": now.isoformat(),
    "fixtureCount": len(fixtures),
    "fixtures": fixtures
}
Path("docs/data").mkdir(parents=True, exist_ok=True)
Path("docs/data/fixtures.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved {len(fixtures)} real fixtures for ConC Soccer day {start_date}: 06:00 EAT to 05:59 EAT next day")

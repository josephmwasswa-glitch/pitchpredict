import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Build recent team form from SportScore's documented day-by-day results endpoint.
# 35 daily requests per run; the free anonymous tier allows substantially more.
TODAY = datetime.now(timezone.utc).date()
DAYS = 35
BASE = "https://sportscore.com/api/v1/fixtures/"
HEADERS = {"Accept": "application/json", "User-Agent": "ConCSoccer/1.0"}

def first(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        value = obj.get(key)
        if value is not None and value != "":
            return value
    return None

def team_name(value):
    if isinstance(value, dict):
        return first(value, "name", "title", "display_name", "short_name")
    return value

def unpack(payload):
    rows = payload if isinstance(payload, list) else first(payload, "matches", "fixtures", "data", "results")
    if isinstance(rows, dict):
        rows = first(rows, "matches", "fixtures", "data", "results")
    return rows if isinstance(rows, list) else []

all_matches = []
errors = []
for offset in range(DAYS):
    day = TODAY - timedelta(days=offset)
    url = f"{BASE}?sport=football&date={day.isoformat()}&status=finished&limit=200"
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        for item in unpack(payload):
            if not isinstance(item, dict):
                continue
            home = team_name(first(item, "home", "home_team", "homeTeam", "team_home"))
            away = team_name(first(item, "away", "away_team", "awayTeam", "team_away"))
            if not home or not away:
                teams = item.get("teams") or {}
                home = home or team_name(first(teams, "home", "local"))
                away = away or team_name(first(teams, "away", "visitor"))
            score = item.get("score") or {}
            hg = first(item, "home_score", "homeGoals", "goals_home")
            ag = first(item, "away_score", "awayGoals", "goals_away")
            if isinstance(score, dict):
                hg = hg if hg is not None else first(score, "home", "home_score", "homeGoals")
                ag = ag if ag is not None else first(score, "away", "away_score", "awayGoals")
            status = first(item, "status", "state", "match_status") or ""
            if isinstance(status, dict):
                status = first(status, "name", "long", "short") or ""
            if not home or not away or hg is None or ag is None:
                continue
            try:
                hg, ag = int(hg), int(ag)
            except (TypeError, ValueError):
                continue
            # A status filter is requested; still reject non-final statuses defensively.
            status_text = str(status).strip().lower()
            if status_text and not any(x in status_text for x in ("finished", "full time", "ft", "after extra", "pen")):
                continue
            competition = item.get("competition") or item.get("league") or {}
            league = first(competition, "name", "title", "short_name") if isinstance(competition, dict) else competition
            match_date = first(item, "date", "kickoff", "kickoff_time", "start_time", "utc_date", "time") or day.isoformat()
            all_matches.append({
                "date": str(match_date), "home": str(home), "away": str(away),
                "homeGoals": hg, "awayGoals": ag, "league": str(league or "Unknown"),
                "status": str(status)
            })
    except Exception as exc:
        errors.append(f"{day.isoformat()}: {exc}")

# Keep latest ten results per team; same match is represented for both sides.
team_rows = {}
league_totals = {}
for match in all_matches:
    for team, gf, ga, venue in (
        (match["home"], match["homeGoals"], match["awayGoals"], "home"),
        (match["away"], match["awayGoals"], match["homeGoals"], "away")
    ):
        team_rows.setdefault(team, []).append({
            "gf": gf, "ga": ga, "venue": venue, "date": match["date"]
        })
    lg = league_totals.setdefault(match["league"], {"goals": 0, "teams": 0, "home_goals": 0, "matches": 0})
    lg["goals"] += match["homeGoals"] + match["awayGoals"]
    lg["teams"] += 2
    lg["home_goals"] += match["homeGoals"]
    lg["matches"] += 1

teams = {}
for team, rows in team_rows.items():
    rows.sort(key=lambda x: x["date"], reverse=True)
    teams[team] = {"matches": rows[:10]}

league_averages = {}
for league, totals in league_totals.items():
    if totals["teams"]:
        overall = totals["goals"] / totals["teams"]
        home_avg = totals["home_goals"] / totals["matches"] if totals["matches"] else overall
        away_avg = (totals["goals"] - totals["home_goals"]) / totals["matches"] if totals["matches"] else overall
        factor = home_avg / away_avg if away_avg else 1.08
        league_averages[league] = {
            "goals_per_team": round(overall, 3),
            "home_factor": round(max(0.85, min(1.25, factor)), 3)
        }

output = {
    "source": "SportScore",
    "sourceUrl": "https://sportscore.com/developers/api/",
    "windowDays": DAYS,
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "completedMatches": len(all_matches),
    "teamCount": len(teams),
    "teams": teams,
    "league_averages": league_averages,
    "fetchWarnings": errors[:5]
}
Path("docs/data").mkdir(parents=True, exist_ok=True)
Path("docs/data/team_history.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved {len(all_matches)} completed matches for {len(teams)} teams from {DAYS} days.")
if errors:
    print(f"Warning: {len(errors)} daily requests failed; first: {errors[0]}")

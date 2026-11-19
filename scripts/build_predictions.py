import json, math
from pathlib import Path

FIXTURES = Path("docs/data/fixtures.json")
HISTORY = Path("docs/data/team_history.json")
OUT = Path("docs/data/predictions.json")

def poisson(lam, k):
    return math.exp(-lam) * lam**k / math.factorial(k)

def probs_for(lh, la):
    scores = {(h,a): poisson(lh,h)*poisson(la,a) for h in range(9) for a in range(9)}
    total = sum(scores.values())
    scores = {k:v/total for k,v in scores.items()}
    p1=sum(p for (h,a),p in scores.items() if h>a)
    px=sum(p for (h,a),p in scores.items() if h==a)
    p2=sum(p for (h,a),p in scores.items() if h<a)
    btts=sum(p for (h,a),p in scores.items() if h>0 and a>0)
    over15=sum(p for (h,a),p in scores.items() if h+a>=2)
    over25=sum(p for (h,a),p in scores.items() if h+a>=3)
    markets = {
      "1":p1,"X":px,"2":p2,"1X":p1+px,"X2":px+p2,"12":p1+p2,
      "BTTS Yes":btts,"BTTS No":1-btts,
      "Over 1.5":over15,"Under 1.5":1-over15,
      "Over 2.5":over25,"Under 2.5":1-over25,
      "1 + Over 2.5":sum(p for (h,a),p in scores.items() if h>a and h+a>=3),
      "2 + Over 2.5":sum(p for (h,a),p in scores.items() if h<a and h+a>=3),
      "1X + Over 2.5":sum(p for (h,a),p in scores.items() if h>=a and h+a>=3),
      "X2 + Over 2.5":sum(p for (h,a),p in scores.items() if h<=a and h+a>=3),
      "1X + Over 1.5":sum(p for (h,a),p in scores.items() if h>=a and h+a>=2),
      "X2 + Over 1.5":sum(p for (h,a),p in scores.items() if h<=a and h+a>=2),
      "BTTS + Over 2.5":sum(p for (h,a),p in scores.items() if h>0 and a>0 and h+a>=3),
      "Home win + BTTS":sum(p for (h,a),p in scores.items() if h>a and h>0 and a>0),
      "Away win + BTTS":sum(p for (h,a),p in scores.items() if h<a and h>0 and a>0),
      "1X + BTTS":sum(p for (h,a),p in scores.items() if h>=a and h>0 and a>0),
      "X2 + BTTS":sum(p for (h,a),p in scores.items() if h<=a and h>0 and a>0),
    }
    return markets

def main():
    if not FIXTURES.exists():
        raise SystemExit("No fixture feed found")
    data=json.loads(FIXTURES.read_text())
    history=json.loads(HISTORY.read_text()) if HISTORY.exists() else {"teams":{},"league_averages":{}}
    teams=history.get("teams",{})
    output=[]
    for f in data.get("fixtures",[]):
        home,away=f.get("home"),f.get("away")
        h=teams.get(home) or {}; a=teams.get(away) or {}
        # History schema: each team has matches=[{gf,ga,venue:'home'|'away'}]
        hm=h.get("matches",[]); am=a.get("matches",[])
        if len(hm)<5 or len(am)<5:
            output.append({"fixtureId":f.get("id"),"home":home,"away":away,"status":"insufficient_history","message":"At least five recent scored results per team are required. No prediction published."})
            continue
        league=history.get("league_averages",{}).get(f.get("league"),{})
        avg= float(league.get("goals_per_team",1.35))
        def mean(rows,key):
            vals=[float(x[key]) for x in rows if x.get(key) is not None]
            return sum(vals)/len(vals) if vals else avg
        h_attack=mean(hm,"gf")/avg; h_def=mean(hm,"ga")/avg
        a_attack=mean(am,"gf")/avg; a_def=mean(am,"ga")/avg
        home_factor=float(league.get("home_factor",1.08))
        lh=max(.15,min(4.5,avg*h_attack*a_def*home_factor))
        la=max(.15,min(4.5,avg*a_attack*h_def/home_factor))
        markets=probs_for(lh,la)
        best=max(markets.items(),key=lambda x:x[1])
        output.append({
          "fixtureId":f.get("id"),"home":home,"away":away,"status":"model_ready",
          "model":"ConC Poisson v1","sample":{"homeTeamMatches":len(hm),"awayTeamMatches":len(am)},
          "expectedGoals":{"home":round(lh,2),"away":round(la,2)},
          "probabilities":{k:round(v*100,1) for k,v in markets.items()},
          "topProbabilityMarket":best[0],"topProbability":round(best[1]*100,1),
          "disclaimer":"Model estimate, not a guarantee. Probabilities are not value assessments; odds are required for value."
        })
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({"date":data.get("date"),"model":"ConC Poisson v1","historySource":"team_history.json","generatedAt":data.get("fetchedAt"),"predictionCount":sum(1 for x in output if x["status"]=="model_ready"),"fixtures":output},ensure_ascii=False,indent=2))
    print(f"Built {sum(1 for x in output if x['status']=='model_ready')} predictions; {len(output)} fixtures checked.")
if __name__=="__main__": main()

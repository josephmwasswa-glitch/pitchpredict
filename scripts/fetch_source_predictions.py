#!/usr/bin/env python3
"""Fetch only publicly accessible, robots-permitted forecast pages.
Unparseable or absent forecasts remain missing; never manufacture a source vote.
"""
import json, re, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

OUT=Path("docs/data/source_predictions.json")
UA="ConCSoccer/1.0 (+https://josephmwasswa-glitch.github.io/pitchpredict/)"
SOURCES={
 "sports_mole":"https://www.sportsmole.co.uk/football/",
 "soccer_vista":"https://www.soccervista.com/predictions/",
 "forebet":"https://www.forebet.com/en/football-predictions"
}
class TextParser(HTMLParser):
 def __init__(self):
  super().__init__(); self.text=[]; self.links=[]; self.skip=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ("script","style","noscript"): self.skip+=1
  if tag=="a" and a.get("href"): self.links.append(a["href"])
 def handle_endtag(self,tag):
  if tag in ("script","style","noscript") and self.skip: self.skip-=1
 def handle_data(self,data):
  if not self.skip and data.strip(): self.text.append(data.strip())
def fetch(url):
 host=urlparse(url).scheme+"://"+urlparse(url).netloc
 rp=urllib.robotparser.RobotFileParser(); rp.set_url(host+"/robots.txt")
 try: rp.read()
 except Exception: return None,"robots_unavailable"
 if not rp.can_fetch(UA,url): return None,"robots_disallow"
 req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html"})
 try:
  with urllib.request.urlopen(req,timeout=25) as r: return r.read().decode("utf-8","replace"),"ok"
 except Exception as e: return None,"fetch_error:"+type(e).__name__
def clean(s):
 return re.sub(r"\s+"," ",s or "").strip()
def team_norm(s):
 return re.sub(r"[^a-z0-9]","",s.lower())
def main():
 now=datetime.now(timezone.utc).isoformat()
 out={"fetchedAt":now,"timezone":"UTC","sources":{},"forecasts":[],"note":"Only explicit, matched public forecasts are counted. Missing data is not a negative vote."}
 # Sports Mole: only article pages with an explicit 'We say: Home 1-0 Away' scoreline.
 url=SOURCES["sports_mole"]; html,status=fetch(url); sm={"url":url,"status":status,"forecastCount":0}
 if html:
  p=TextParser(); p.feed(html); links=[]
  for href in p.links:
   full=urljoin(url,href)
   if "sportsmole.co.uk/football/" in full and "/preview/" in full and full not in links: links.append(full)
  for article in links[:35]:
   body,st=fetch(article)
   if not body: continue
   q=TextParser(); q.feed(body); txt=clean(" ".join(q.text))
   m=re.search(r"We say:\s*:?\s*(.{2,90}?)\s+(\d{1,2})\s*[-–:]\s*(\d{1,2})\s+(.{2,90}?)(?:\s+(?:in|at|on|to|for)\s+|$)",txt,re.I)
   if not m: continue
   home,hs,as_,away=m.groups()
   out["forecasts"].append({"source":"sports_mole","home":clean(home),"away":clean(away),"score":{"home":int(hs),"away":int(as_)},"url":article,"marketPicks":{"1X2":"1" if int(hs)>int(as_) else "2" if int(hs)<int(as_) else "X","Over/Under 2.5":"Over 2.5" if int(hs)+int(as_)>=3 else "Under 2.5"},"derivation":"Derived only from the publisher's explicit predicted scoreline."})
  sm["forecastCount"]=sum(x["source"]=="sports_mole" for x in out["forecasts"])
  if sm["forecastCount"]: sm["status"]="ok"
  elif status=="ok": sm["status"]="page_read_no_verified_scorelines"
 out["sources"]["sports_mole"]=sm
 # Read the other two publisher pages and report availability; no speculative parsing.
 for key in ("soccer_vista","forebet"):
  url=SOURCES[key]; body,status=fetch(url)
  out["sources"][key]={"url":url,"status":status if not body else "page_read_no_verified_rows","forecastCount":0}
  if body:
   out["sources"][key]["pageBytes"]=len(body)
   out["sources"][key]["note"]="Public page retrieved, but no match rows are published to consensus until a reliable match-specific parser is validated."
 OUT.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
 print("Source checks: "+", ".join(k+"="+v["status"]+" ("+str(v["forecastCount"])+")" for k,v in out["sources"].items()))
 print("Verified Sports Mole scoreline forecasts:",len(out["forecasts"]))
if __name__=="__main__": main()

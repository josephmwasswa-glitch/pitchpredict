# PitchPredict / Kataka football predictions

AI-assisted football analysis and prediction platform.

## Four-source consensus

The API now exposes a four-source consensus registry:

- Forebet
- Sports Mole
- SoccerVista
- Kataka statistical model (the internal model source, previously labelled GoalWise AI in the API)

### API endpoints

- `GET /consensus/sources` — lists the configured source names and official starting pages.
- `POST /consensus/evaluate` — compares fixture-specific source picks.
- `POST /consensus/ai-predict` — generates Kataka AI's independent statistical pick.
- `POST /consensus/evaluate-with-ai` — generates Kataka AI's pick and combines it with the submitted Forebet, Sports Mole and/or SoccerVista picks.

Example request:

```json
{
  "fixture_id": "fixture-123",
  "home_team": "Home FC",
  "away_team": "Away FC",
  "market": "1X2",
  "predictions": [
    {"source": "forebet", "selection": "Home"},
    {"source": "sports_mole", "selection": "Home", "source_url": "https://www.sportsmole.co.uk/football/preview/"},
    {"source": "soccervista", "selection": "Home", "source_url": "https://www.soccervista.com/"},
    {"source": "kataka_ai", "selection": "Home", "confidence": 62}
  ]
}
```

### Consensus labels

- `4/4`: unanimous agreement.
- `3/4`: strong consensus.
- `2/4`: review only; not promoted as a recommended shortlist pick.
- `1/4`: exclude.
- Ties: no consensus selection.

Each source can vote once. Duplicate source submissions are rejected. A missing source is shown in `missing_sources`, not treated as a vote against the pick. The confidence field is the mean of supplied confidence values from supporting sources; it is not a calibrated probability.

## Integration status and limitations

The API now accepts and evaluates predictions from all four named sources and publishes their official starting pages. This commit does **not** implement verified automatic extraction of fixture-specific picks from the Sports Mole or SoccerVista websites. Their public pages have different editorial/data layouts and should not be treated as structured APIs. A source pick must be captured from the correct fixture page and submitted with its source URL and retrieval time. Do not fill missing predictions with guesses.

Sports Mole publishes editorial previews and predictions: https://www.sportsmole.co.uk/football/preview/

SoccerVista publishes football forecasts and match statistics: https://www.soccervista.com/

SoccerVista currently displays a notice that it plans to move to SoccerWay on 16 December; its connector should be rechecked after that date.

Source agreement is not certainty. Keep historical picks timestamped and retain losing results when measuring accuracy.


## Kataka AI prediction endpoint

Set FOOTBALL_API_KEY (or API_FOOTBALL_KEY) as a private backend environment variable using an API-Football key. Never expose this key in frontend code.

Generate an independent model pick with POST /consensus/ai-predict. JSON request:

    {"home_team":"Arsenal","away_team":"Chelsea","market":"1X2"}

Markets supported: 1X2, BTTS, OVER 1.5, OVER 2.5, OVER 3.5, and DOUBLE CHANCE.

To generate Kataka AI's prediction and calculate source consensus in one request, use POST /consensus/evaluate-with-ai. Example request:

    {
      "fixture_id": "fixture-123",
      "home_team": "Arsenal",
      "away_team": "Chelsea",
      "market": "OVER 2.5",
      "predictions": [
        {"source": "forebet", "selection": "Over 2.5"},
        {"source": "sports_mole", "selection": "Over 2.5", "source_url": "https://www.sportsmole.co.uk/football/preview/"},
        {"source": "soccervista", "selection": "Over 2.5", "source_url": "https://www.soccervista.com/"}
      ]
    }

This endpoint calculates the fourth (Kataka AI) pick itself. The three external picks still have to be retrieved and verified from actual fixture-specific source pages; this endpoint does not scrape those websites. If fewer external picks are supplied, missing sources are reported and never counted as agreement.

The current AI model is a transparent recent-form Poisson statistical model using completed team matches fetched from API-Football. It is not a trained machine-learning model and its confidence is not yet calibrated by a historical backtest. It requires at least three completed matches per team; if the API key is missing or data is insufficient, it returns an error rather than inventing a prediction. Injuries, confirmed lineups, weather and odds are not currently included.

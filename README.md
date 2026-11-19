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
    {"source": "goalwise_ai", "selection": "Home", "confidence": 62}
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

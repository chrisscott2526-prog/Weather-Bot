name: Log nightly forecasts

on:
  schedule:
    - cron: "0 23 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  forecast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - name: Fetch forecasts
        run: python forecast.py

      - name: Commit the log
        run: |
          git config user.name "weather-bot"
          git config user.email "bot@users.noreply.github.com"
          git add forecasts.csv
          git diff --cached --quiet || git commit -m "forecasts $(date -u +'%F')"
          git push

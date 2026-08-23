"""Weather-Bot: single source of truth for all 20 Kalshi temperature
cities. Import this from poller.py, forecast.py, and scanner.py so
every script agrees on names and stations.

STATION = the observation station each market's rules panel points at
via its CLI code (the trick: CLIPHX -- CLI plus the station letters.
Match it to the station here). Settlement is officially The Weather
Company's reported max for that station: the Aug 23 2026 audit found
all 20 rules panels name TWC as the official source, none the NWS
(see RULES_AUDIT_FINDINGS.md). The NWS station observations are TWC's
underlying source, so the station mapping is still what makes or
breaks calibration. All 20 verified by hand Aug 3 2026 and re-verified
against the live CLI codes Aug 23 2026.
Wrong station = garbage calibration = losing trades.
Known Kalshi gotchas already baked in: Chicago=Midway, Dallas=DFW,
Houston=Hobby (NOT Intercontinental).
"""

# series_ticker: (city_name, icao_station, lat, lon, needs_verification)
CITIES = {
    # --- the original 7, settling correctly since day one ---
    "KXHIGHNY":   ("New York City", "KNYC", 40.7794,  -73.9692, False),
    "KXHIGHMIA":  ("Miami",         "KMIA", 25.7906,  -80.3164, False),
    "KXHIGHDEN":  ("Denver",        "KDEN", 39.8467, -104.6562, False),
    "KXHIGHLAX":  ("Los Angeles",   "KLAX", 33.9382, -118.3866, False),
    "KXHIGHPHIL": ("Philadelphia",  "KPHL", 39.8683,  -75.2311, False),
    "KXHIGHAUS":  ("Austin",        "KAUS", 30.1945,  -97.6699, False),
    "KXHIGHCHI":  ("Chicago",       "KMDW", 41.7842,  -87.7553, False),
    # --- the other 13; series tickers corrected from trades.csv Aug 3 ---
    "KXHIGHTSFO": ("San Francisco", "KSFO", 37.6188, -122.3750, False),
    "KXHIGHTPHX": ("Phoenix",       "KPHX", 33.4278, -112.0038, False),
    "KXHIGHTDC":  ("Washington DC", "KDCA", 38.8512,  -77.0402, False),
    "KXHIGHTATL": ("Atlanta",       "KATL", 33.6301,  -84.4418, False),
    "KXHIGHTDAL": ("Dallas",        "KDFW", 32.8998,  -97.0403, False),
    "KXHIGHTSEA": ("Seattle",       "KSEA", 47.4444, -122.3139, False),
    "KXHIGHTLV":  ("Las Vegas",     "KLAS", 36.0719, -115.1634, False),
    "KXHIGHTOKC": ("Oklahoma City", "KOKC", 35.3889,  -97.6006, False),
    "KXHIGHTBOS": ("Boston",        "KBOS", 42.3606,  -71.0097, False),
    "KXHIGHTMIN": ("Minneapolis",   "KMSP", 44.8848,  -93.2223, False),
    "KXHIGHTSATX":("San Antonio",   "KSAT", 29.5443,  -98.4839, False),
    "KXHIGHTNOLA":("New Orleans",   "KMSY", 29.9934,  -90.2509, False),
    "KXHIGHTHOU": ("Houston",       "KHOU", 29.6375,  -95.2825, False),
}

# Ghost series seen on Kalshi with 0 open markets (Aug 5 2026):
# KXHIGHNYD, KXHIGHOU, KXHIGHTEMPDEN, KXHIGHUS.
# They are NOT in CITIES on purpose. If one ever shows open markets,
# verify its station on Kalshi before adding it -- do not let discovery
# code auto-match it.

SERIES_TO_CITY = {k: v[0] for k, v in CITIES.items()}
CITY_TO_STATION = {v[0]: v[1] for v in CITIES.values()}
# poller.py:   station -> city
STATIONS = {v[1]: v[0] for v in CITIES.values()}
# forecast.py: station -> (city, lat, lon)
SITES = {v[1]: (v[0], v[2], v[3]) for v in CITIES.values()}
UNVERIFIED = sorted(v[0] for v in CITIES.values() if v[4])


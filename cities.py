"""Weather-Bot: single source of truth for all 20 Kalshi temperature
cities. Import this from poller.py, forecast.py, and scanner.py so
every script agrees on names and stations.

STATION = the NWS station whose Daily Climate Report settles the
market. VERIFY=True means: open that city's market on Kalshi, check
the rules/underlying section, and confirm the station before trusting
its data. Wrong station = garbage calibration = losing trades.
Known Kalshi gotchas already baked in: Chicago=Midway, Dallas=DFW,
Houston=Hobby (NOT Intercontinental).
"""

# series_ticker: (city_name, icao_station, lat, lon, needs_verification)
CITIES = {
    # --- your original 7, already settling correctly ---
    "KXHIGHNY":   ("New York City", "KNYC", 40.7794,  -73.9692, False),
    "KXHIGHMIA":  ("Miami",         "KMIA", 25.7906,  -80.3164, False),
    "KXHIGHDEN":  ("Denver",        "KDEN", 39.8467, -104.6562, False),
    "KXHIGHLAX":  ("Los Angeles",   "KLAX", 33.9382, -118.3866, False),
    "KXHIGHPHIL": ("Philadelphia",  "KPHL", 39.8683,  -75.2311, False),
    "KXHIGHAUS":  ("Austin",        "KAUS", 30.1945,  -97.6699, False),
    "KXHIGHCHI":  ("Chicago",       "KMDW", 41.7842,  -87.7553, False),
    # --- the other 13; VERIFY series ticker AND station on Kalshi ---
    "KXHIGHSF":   ("San Francisco", "KSFO", 37.6188, -122.3750, True),
    "KXHIGHPHX":  ("Phoenix",       "KPHX", 33.4278, -112.0038, True),
    "KXHIGHDC":   ("Washington DC", "KDCA", 38.8512,  -77.0402, True),
    "KXHIGHATL":  ("Atlanta",       "KATL", 33.6301,  -84.4418, True),
    "KXHIGHDFW":  ("Dallas",        "KDFW", 32.8998,  -97.0403, True),
    "KXHIGHSEA":  ("Seattle",       "KSEA", 47.4444, -122.3139, True),
    "KXHIGHLV":   ("Las Vegas",     "KLAS", 36.0719, -115.1634, True),
    "KXHIGHOKC":  ("Oklahoma City", "KOKC", 35.3889,  -97.6006, True),
    "KXHIGHBOS":  ("Boston",        "KBOS", 42.3606,  -71.0097, True),
    "KXHIGHMSP":  ("Minneapolis",   "KMSP", 44.8848,  -93.2223, True),
    "KXHIGHSAT":  ("San Antonio",   "KSAT", 29.5443,  -98.4839, True),
    "KXHIGHMSY":  ("New Orleans",   "KMSY", 29.9934,  -90.2509, True),
    "KXHIGHHOU":  ("Houston",       "KHOU", 29.6375,  -95.2825, True),
}

SERIES_TO_CITY = {k: v[0] for k, v in CITIES.items()}
CITY_TO_STATION = {v[0]: v[1] for v in CITIES.values()}
# poller.py:   station -> city
STATIONS = {v[1]: v[0] for v in CITIES.values()}
# forecast.py: station -> (city, lat, lon)
SITES = {v[1]: (v[0], v[2], v[3]) for v in CITIES.values()}
UNVERIFIED = sorted(v[0] for v in CITIES.values() if v[4])

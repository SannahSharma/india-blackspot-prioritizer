from pathlib import Path

# Project folder locations
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"

# Make sure the data folders exist
for folder in (RAW, INTERIM, PROCESSED):
    folder.mkdir(parents=True, exist_ok=True)

# Map settings (used later)
CRS_WGS84 = "EPSG:4326"          # normal latitude/longitude
CRS_INDIA_METRIC = "EPSG:7755"   # India map projection in metres, for measuring distances
MATCH_RADIUS_M = 2000            # how close (in metres) a hotspot must be to a black spot to count as a match
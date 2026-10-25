import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.config import RAW

crash_file = next((RAW / "toi_crashes").rglob("News Crashes.xlsx"))
crashes = pd.read_excel(crash_file)
crashes.columns = crashes.columns.str.strip()   # remove extra spaces in column names

# 1. Every unique value in the category columns, with counts
for col in ["Road Type", "Crash Type", "Vehicle 1", "Vehicle/Object 2", "State"]:
    print("=" * 60)
    print(col)
    print(crashes[col].astype(str).str.strip().value_counts().to_string())

# 2. Split "lat, lon" text into two number columns
parts = crashes["LatLong"].astype(str).str.split(",", n=1, expand=True)
crashes["lat"] = pd.to_numeric(parts[0], errors="coerce")
crashes["lon"] = pd.to_numeric(parts[1], errors="coerce")

print("=" * 60)
print("COORDINATES")
print("Could not read:", crashes["lat"].isna().sum() + crashes["lon"].isna().sum())
print("Lat range:", crashes["lat"].min(), "to", crashes["lat"].max())
print("Lon range:", crashes["lon"].min(), "to", crashes["lon"].max())
outside = ~crashes["lat"].between(6, 37.5) | ~crashes["lon"].between(68, 97.5)
print("Outside India's bounding box:", outside.sum())

# 3. Are many crashes sharing the exact same point? (a sign of town-centre geocoding)
coords = crashes["lat"].round(5).astype(str) + "," + crashes["lon"].round(5).astype(str)
print("Unique coordinate points:", coords.nunique(), "out of", len(crashes))
print("Most repeated points:")
print(coords.value_counts().head(10).to_string())

# 4. Deaths and injuries
print("=" * 60)
print(crashes[["Killed", "Injured"]].describe().to_string())
print("Total killed:", crashes["Killed"].sum(), "| Total injured:", crashes["Injured"].sum())

# 5. Dates: find values that are not real dates
print("=" * 60)
print("DATES")
dates = pd.to_datetime(crashes["Crash Date"], errors="coerce")
bad = dates.isna()
print("Dates that could not be read:", bad.sum())
print(crashes.loc[bad, ["S. No.", "Crash Date", "Article Date"]].head(20).to_string())
print("Readable dates range:", dates.min(), "to", dates.max())
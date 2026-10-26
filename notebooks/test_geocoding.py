import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from src.config import RAW, INTERIM

# 1. Load and give the columns short names
bs = pd.read_csv(RAW / "blackspots_top10.csv", encoding="latin-1")
bs.columns = ["state", "district", "police_station", "road", "location",
              "km_start", "km_end",
              "acc_2016", "acc_2017", "acc_2018", "acc_total",
              "fat_2016", "fat_2017", "fat_2018", "fat_total"]

# 2. Basic text tidy-up
for col in ["state", "district", "police_station", "road", "location"]:
    bs[col] = (bs[col].fillna("").astype(str)
               .str.replace(r"\s+", " ", regex=True).str.strip())
bs["police_station"] = bs["police_station"].str.replace(r"\s*P\.?S\.?$", "", regex=True)
# "A to B" -> "A";  remove "Near "
bs["location_main"] = (bs["location"].str.split(r"\s+to\s+", regex=True).str[0]
                       .str.replace(r"^(near|nr\.?)\s+", "", case=False, regex=True))

print("Black spots per state:")
print(bs["state"].value_counts().to_string())

# 3. Set up the free OpenStreetMap geocoder (max 1 request per second)
geolocator = Nominatim(user_agent="india-blackspot-prioritizer-student-project")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1)

def try_geocode(row):
    """Try from most precise to least precise; return the first hit."""
    attempts = [
        ("location+district", f"{row.location_main}, {row.district}, {row.state}, India"),
        ("location+state",    f"{row.location_main}, {row.state}, India"),
    ]
    if row.police_station:
        attempts.append(("police_station", f"{row.police_station}, {row.district}, {row.state}, India"))
    for level, query in attempts:
        res = geocode(query, country_codes="in", addressdetails=True, language="en")
        if res:
            got_state = res.raw.get("address", {}).get("state", "")
            return pd.Series({"level": level, "lat": res.latitude, "lon": res.longitude,
                              "osm_state": got_state, "osm_address": res.address})
    return pd.Series({"level": "failed", "lat": None, "lon": None,
                      "osm_state": "", "osm_address": ""})

# 4. Test on 20 random black spots (takes about 1 minute)
sample = bs.sample(20, random_state=42).reset_index(drop=True)
print("\nGeocoding 20 black spots... please wait about a minute")
results = sample.apply(try_geocode, axis=1)
out = pd.concat([sample[["state", "district", "police_station", "location"]], results], axis=1)

# 5. Did the result land in the right state?
out["state_match"] = out.apply(
    lambda r: r.state.lower()[:5] in str(r.osm_state).lower(), axis=1)

pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 35)
print(out[["state", "location", "level", "osm_state", "state_match"]].to_string())
print("\nResult by level:")
print(out["level"].value_counts().to_string())
print("Landed in the correct state:", out["state_match"].sum(), "of", len(out))

out.to_csv(INTERIM / "geocode_test.csv", index=False)
print("Saved to data/interim/geocode_test.csv")
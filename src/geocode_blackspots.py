"""Geocode official black spots with validation and confidence levels.

Every result must (1) resemble the searched name and (2) fall near the
police station / district, otherwise it is rejected.

Usage:
    python src/geocode_blackspots.py --sample 20   # quick test
    python src/geocode_blackspots.py               # all black spots
"""
import argparse
import difflib
import math
import re
import sys
from functools import lru_cache
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from geopy.geocoders import Nominatim, Photon
from geopy.extra.rate_limiter import RateLimiter
from src.config import RAW, INTERIM

COLS = ["state", "district", "police_station", "road", "location",
        "km_start", "km_end",
        "acc_2016", "acc_2017", "acc_2018", "acc_total",
        "fat_2016", "fat_2017", "fat_2018", "fat_total"]

STATE_FIXES = {
    "Maharastra": "Maharashtra", "Tamilnadu": "Tamil Nadu", "Orrisha": "Odisha",
    "Uttrakhand": "Uttarakhand", "Chhattishgarh": "Chhattisgarh",
    "Megahalaya": "Meghalaya",
}

# Abbreviated / misspelled / police-unit district names -> real district names
DISTRICT_FIXES = {
    "EG": "East Godavari", "WG Dist": "West Godavari", "UDN": "Udham Singh Nagar",
    "UKI": "Uttarkashi", "ALM": "Almora", "NTL": "Nainital", "SPJ": "Sepahijala",
    "Dhalal": "Dhalai", "Devash": "Dewas", "Udaypur": "Udaipur",
    "Mayurabhanj": "Mayurbhanj", "Bengalurr city": "Bengaluru",
    "MUJAFFARNAGR": "Muzaffarnagar", "Muradabad": "Moradabad", "Mandsore": "Mandsaur",
    "Nimach": "Neemuch", "Sarguja": "Surguja", "Jaipur Gramin": "Jaipur",
    "Jaipur Purva": "Jaipur", "Rachakonda": "Hyderabad", "Cyberabad": "Hyderabad",
    "Naugachia": "Bhagalpur", "Baddi": "Solan", "COP/ Ludhiana": "Ludhiana",
    "UPD bhubaneaswar": "Bhubaneswar", "Howrah PC": "Howrah", "Howrah Rural": "Howrah",
    "Asansol-Durgapur PC": "Paschim Bardhaman", "Jowai traffic Branch": "West Jaintia Hills",
    "Papum Pare (Capital)": "Papum Pare", "CITY GUWAHATI": "Guwahati",
    "Chennai City": "Chennai", "Guntur Urban": "Guntur",
    "Amaravati City": "Amravati", "Amravati Rural": "Amravati",
}

# Words too common to prove a match ("Katsar Village" must match on "Katsar")
GENERIC = {
    "village", "road", "chowk", "cross", "bridge", "near", "station", "metro",
    "petrol", "pump", "bunk", "toll", "gate", "bypass", "junction", "border", "ramp",
    "chungi", "flyover", "post", "office", "area", "taluka", "traffic", "police",
    "division", "main", "highway", "circle", "square", "more", "point", "stand",
    "motor", "market", "bazar", "bazaar", "hospital", "school", "temple",
    "national", "district", "city", "rural",
}

MAX_KM_FROM_POLICE_STATION = 15
MAX_KM_FROM_DISTRICT = 40
MAX_KM_POLICE_STATION_FROM_DISTRICT = 60

USER_AGENT = "india-blackspot-prioritizer-student-project"


# ---------- 1. Load and tidy ----------
def load_blackspots() -> pd.DataFrame:
    bs = pd.read_csv(RAW / "blackspots_top10.csv", encoding="latin-1")
    bs.columns = COLS
    for col in ["state", "district", "police_station", "road", "location"]:
        bs[col] = (bs[col].fillna("").astype(str)
                   .str.replace(r"\s+", " ", regex=True).str.strip())
    bs["state"] = bs["state"].replace(STATE_FIXES)
    bs["police_station"] = (bs["police_station"]
                            .str.replace(r"^P\.?S\.?[\s\-]*", "", case=False, regex=True)
                            .str.replace(r"\s*\bP\.?\s?S\.?$", "", case=False, regex=True))
    bs["district_clean"] = (bs["district"].replace(DISTRICT_FIXES)
                            .str.replace(r"\b(district|distt\.?|dist|rural|city|urban)\b",
                                         "", case=False, regex=True)
                            .str.replace(r"\s+", " ", regex=True).str.strip(" .,"))
    bs.insert(0, "blackspot_id", range(1, len(bs) + 1))
    return bs


def name_variants(location: str) -> list[str]:
    """Turn a messy location string into up to 3 clean search names."""
    text = re.sub(r"\(.*?\)", " ", location)
    text = re.sub(r"\b(NH|SH)[\s\-\.]*\d+\w*", " ", text, flags=re.I)
    text = re.sub(r"\b(near|nr\.?|opp\.?|opposite)\b", " ", text, flags=re.I)
    text = re.sub(r"\d+(\.\d+)?\s*(km|kms|mtr|mtrs|m)\b\.?", " ", text, flags=re.I)
    full = re.sub(r"\s+", " ", text).strip(" ,-.")
    parts = re.split(r",|\s+to\s+|\s+-\s+|/", text, flags=re.I)

    variants = []
    for v in [full] + parts:
        v = re.sub(r"\s+", " ", v).strip(" ,-.")
        if len(v) >= 3 and v.lower() not in [x.lower() for x in variants]:
            variants.append(v)
    return variants[:3]


# ---------- 2. Checks ----------
def words(text) -> list[str]:
    return re.findall(r"[a-z]+", str(text).lower())


def names_match(expected: str, found: str) -> bool:
    """True if a distinctive word from `expected` appears (or nearly appears) in `found`."""
    found_words = words(found)
    if not found_words:
        return False
    key = [w for w in words(expected) if len(w) > 3 and w not in GENERIC]
    if not key:
        key = [w for w in words(expected) if len(w) > 1]
    for k in key:
        for f in found_words:
            if k == f or (len(k) > 4 and difflib.SequenceMatcher(None, k, f).ratio() >= 0.8):
                return True
    return False


def same_state(expected: str, got: str) -> bool:
    return expected.lower()[:5] in (got or "").lower()


def km_between(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(h))


# ---------- 3. Geocoders (both free, OpenStreetMap-based, 1 request/second) ----------
_nom = Nominatim(user_agent=USER_AGENT, timeout=10)
_pho = Photon(user_agent=USER_AGENT, timeout=10)
nom_geocode = RateLimiter(_nom.geocode, min_delay_seconds=1.1,
                          max_retries=2, error_wait_seconds=5, swallow_exceptions=True)
pho_geocode = RateLimiter(_pho.geocode, min_delay_seconds=1.1,
                          max_retries=2, error_wait_seconds=5, swallow_exceptions=True)


@lru_cache(maxsize=None)
def search(query: str, state: str, expected_name: str):
    """First result (Nominatim, then Photon) in the right state whose name
    resembles expected_name. Returns (lat, lon, address, source) or None."""
    for r in nom_geocode(query, exactly_one=False, limit=3, country_codes="in",
                         addressdetails=True, language="en") or []:
        name = r.raw.get("name") or r.address.split(",")[0]
        if (same_state(state, r.raw.get("address", {}).get("state", ""))
                and names_match(expected_name, name)):
            return (r.latitude, r.longitude, r.address, "nominatim")
    for r in pho_geocode(query, exactly_one=False, limit=5, language="en") or []:
        p = r.raw.get("properties", {})
        if (p.get("country") == "India" and same_state(state, p.get("state", ""))
                and names_match(expected_name, p.get("name", ""))):
            return (r.latitude, r.longitude, r.address, "photon")
    return None


def pack(confidence, method, matched_name, hit):
    lat, lon, address, _ = hit if hit else (None, None, "", "")
    return {"confidence": confidence, "method": method, "matched_name": matched_name,
            "lat": lat, "lon": lon, "osm_address": address}


def geocode_row(row) -> dict:
    place = f"{row.district_clean}, {row.state}, India"

    # Anchors used to validate the location result
    district_hit = search(place, row.state, row.district_clean) if row.district_clean else None

    ps_hit = None
    if row.police_station:
        hit = search(f"{row.police_station}, {place}", row.state, row.police_station)
        if hit and (district_hit is None
                    or km_between(hit, district_hit) <= MAX_KM_POLICE_STATION_FROM_DISTRICT):
            ps_hit = hit

    # Try the actual location, accepting it only if it is near an anchor
    for name in name_variants(row.location):
        hit = search(f"{name}, {place}", row.state, name)
        if not hit:
            continue
        if ps_hit:
            if km_between(hit, ps_hit) <= MAX_KM_FROM_POLICE_STATION:
                return pack("high", f"location ({hit[3]}), near police station", name, hit)
        elif district_hit:
            if km_between(hit, district_hit) <= MAX_KM_FROM_DISTRICT:
                return pack("high", f"location ({hit[3]}), near district", name, hit)
        else:
            return pack("medium", f"location ({hit[3]}), unverified", name, hit)
        # otherwise: too far from the anchor -> try the next name variant

    if ps_hit:
        return pack("medium", "police station", row.police_station, ps_hit)
    if district_hit:
        return pack("low", "district", row.district_clean, district_hit)
    return pack("failed", "none", "", None)


# ---------- 4. Run ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=0, help="test on N random rows")
    args = parser.parse_args()

    bs = load_blackspots()
    if args.sample:
        bs = bs.sample(args.sample, random_state=42).reset_index(drop=True)
        out_path = INTERIM / "geocode_test.csv"
    else:
        out_path = INTERIM / "blackspots_geocoded.csv"

    print(f"Geocoding {len(bs)} black spots (about 5-10 seconds each)...")
    results = []
    for i, row in enumerate(bs.itertuples(index=False), start=1):
        results.append(geocode_row(row))
        if i % 10 == 0 or i == len(bs):
            print(f"  {i}/{len(bs)} done")

    out = pd.concat([bs, pd.DataFrame(results)], axis=1)
    out.to_csv(out_path, index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 40)
    if args.sample:
        print(out[["location", "confidence", "method", "osm_address"]].to_string())
    print("\nConfidence levels:")
    print(out["confidence"].value_counts().to_string())
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
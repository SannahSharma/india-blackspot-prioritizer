import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.config import INTERIM

df = pd.read_csv(INTERIM / "geocode_test.csv")

for _, r in df.iterrows():
    print("=" * 90)
    print(f"[{r.confidence}] {r.state} | district: {r.district} | PS: {r.police_station}")
    print("  official location :", repr(r.location))
    print("  searched as       :", repr(r.matched_name))
    print("  map found         :", r.osm_address)
    print(f"  coordinates       : {r.lat}, {r.lon}")
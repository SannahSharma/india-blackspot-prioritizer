import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.config import RAW

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 40)

path = RAW / "blackspots_top10.csv"

# Government CSVs sometimes use unusual text encoding; try a few
for enc in ["utf-8", "utf-8-sig", "latin-1"]:
    try:
        bs = pd.read_csv(path, encoding=enc)
        print("Read with encoding:", enc)
        break
    except UnicodeDecodeError:
        continue

print("Rows, columns:", bs.shape)
print("\nColumns:")
for c in bs.columns:
    print("  -", repr(c))

print("\nFirst 10 rows:")
print(bs.head(10).to_string())

print("\nMissing values per column:")
print(bs.isna().sum().to_string())

print("\nRows per state:")
print(bs.iloc[:, 1].value_counts().to_string())
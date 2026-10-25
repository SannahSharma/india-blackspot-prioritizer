import sys
from pathlib import Path

# Let this script find the src folder
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.config import RAW

# Show all columns when printing
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 250)

# Find the two files, wherever they sit inside toi_crashes
folder = RAW / "toi_crashes"
dict_file = next(folder.rglob("Data Dictionary.xlsx"))
crash_file = next(folder.rglob("News Crashes.xlsx"))

# 1. Data dictionary: print it in full
print("=" * 80)
print("DATA DICTIONARY")
for sheet, df in pd.read_excel(dict_file, sheet_name=None).items():
    print(f"--- sheet: {sheet} ---")
    print(df.to_string())

# 2. Crash data: size, columns, first rows, missing values
crashes = pd.read_excel(crash_file)
print("=" * 80)
print("CRASH DATA")
print("Rows, columns:", crashes.shape)
print("\nColumns:", crashes.columns.tolist())
print("\nFirst 5 rows:")
print(crashes.head().to_string())
print("\nMissing values per column:")
print(crashes.isna().sum().to_string())
"""Clean the Times of India fatal crash dataset (Mendeley, 2022-2023)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.config import RAW, PROCESSED

# Spelling fixes found during exploration
STATE_FIXES = {"Chhatisgarh": "Chhattisgarh", "Jammu": "Jammu & Kashmir"}
CRASH_TYPE_FIXES = {"WIth Parked Vehicle": "With Parked Vehicle"}
ROAD_TYPE_NAMES = {"NH": "National Highway", "SH": "State Highway", "OR": "Other Road"}


def load_raw() -> pd.DataFrame:
    """Read the raw Excel file."""
    path = next((RAW / "toi_crashes").rglob("News Crashes.xlsx"))
    return pd.read_excel(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. Tidy column names: strip spaces, lowercase, use underscores
    df.columns = (df.columns.str.strip().str.lower()
                  .str.replace("/", "_").str.replace(".", "")
                  .str.replace(" ", "_"))
    df = df.rename(columns={"s_no": "crash_id", "vehicle_object_2": "vehicle_2"})

    # 2. Strip stray spaces from all text values
    for col in df.select_dtypes(include=["object", "str"]).columns:
        df[col] = df[col].astype(str).str.strip()

    # 3. Fix spellings and label road types
    df["state"] = df["state"].replace(STATE_FIXES)
    df["crash_type"] = df["crash_type"].replace(CRASH_TYPE_FIXES)
    df["road_type_name"] = df["road_type"].map(ROAD_TYPE_NAMES)

    # 4. "Nil" means "not recorded / not applicable"
    df["million_plus_city"] = df["million_plus_city"].replace("Nil", pd.NA)
    df["vehicle_1"] = df["vehicle_1"].replace("Nil", "Unknown")
    df["vehicle_2"] = df["vehicle_2"].replace("Nil", "None/Single vehicle")

    # 5. Split "lat, lon" into two number columns
    parts = df["latlong"].str.split(",", n=1, expand=True)
    df["lat"] = pd.to_numeric(parts[0], errors="coerce")
    df["lon"] = pd.to_numeric(parts[1], errors="coerce")
    df = df.drop(columns=["latlong"])

    # 6. Proper dates, plus year and month taken from the crash date
    df["crash_date"] = pd.to_datetime(df["crash_date"], errors="coerce")
    df["article_date"] = pd.to_datetime(df["article_date"], errors="coerce")
    df["year"] = df["crash_date"].dt.year
    df["month"] = df["crash_date"].dt.month_name()

    # 7. Keep only rows with valid coordinates inside India
    inside = df["lat"].between(6, 37.5) & df["lon"].between(68, 97.5)
    df = df[inside].reset_index(drop=True)

    # 8. Drop columns we won't use (sparse personal details)
    df = df.drop(columns=["age", "gender"])

    return df


def main():
    raw = load_raw()
    df = clean(raw)
    out = PROCESSED / "crashes_clean.csv"
    df.to_csv(out, index=False)
    print(f"Raw rows: {len(raw)} | Clean rows: {len(df)}")
    print(f"Killed: {df['killed'].sum()} | Injured: {df['injured'].sum()}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Saved to: {out}")


if __name__ == "__main__":
    main()
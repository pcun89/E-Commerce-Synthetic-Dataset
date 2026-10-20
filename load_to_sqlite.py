#!/usr/bin/env python3
"""Load the generated CSVs into a local SQLite database (ecommerce.db)."""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
DB = ROOT / "ecommerce.db"

if DB.exists():
    DB.unlink()

con = sqlite3.connect(DB)
con.executescript((ROOT / "sql" / "schema.sql").read_text())
for table in ("customers", "orders"):
    df = pd.read_csv(ROOT / "data" / f"{table}.csv")
    df.to_sql(table, con, if_exists="append", index=False)
    print(f"loaded {len(df):,} rows into {table}")
con.commit()
con.close()
print(f"created {DB.name}")

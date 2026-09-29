import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


# ============================================================
# 1. PostgreSQL connection
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set.\n"
        "Set it in PowerShell before running this script."
    )

engine = create_engine(DATABASE_URL)


# ============================================================
# 2. Local Data Lake
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "ecommerce-data-lake" / "raw"

TABLES = [
    "users",
    "products",
    "orders",
    "order_items",
    "visits",
]


# ============================================================
# 3. Extract PostgreSQL → Parquet
# ============================================================

def extract_table(table_name):
    output_dir = RAW_DIR / table_name
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nExtracting table: {table_name}")

    query = text(f"SELECT * FROM {table_name}")

    df = pd.read_sql(query, engine)

    output_file = output_dir / f"{table_name}.parquet"

    df.to_parquet(
        output_file,
        engine="pyarrow",
        index=False
    )

    print(f"Rows extracted : {len(df)}")
    print(f"Output file    : {output_file}")


# ============================================================
# 4. Main
# ============================================================

def main():

    print("=" * 60)
    print("POSTGRESQL → LOCAL DATA LAKE INGESTION")
    print("=" * 60)

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        print("PostgreSQL connection: SUCCESS")

        for table in TABLES:
            extract_table(table)

        print("\n" + "=" * 60)
        print("INGESTION COMPLETED SUCCESSFULLY")
        print("=" * 60)

    except Exception as e:
        print("\nINGESTION FAILED")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
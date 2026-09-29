from pathlib import Path
from datetime import datetime, timezone
import uuid

import pandas as pd


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_DIR = BASE_DIR / "ecommerce-data-lake" / "raw"
BRONZE_DIR = BASE_DIR / "ecommerce-data-lake" / "bronze"

TABLES = [
    "users",
    "products",
    "orders",
    "order_items",
    "visits",
]


# ============================================================
# Bronze transformation
# ============================================================

def process_table(table_name, batch_id, ingestion_time):

    raw_file = RAW_DIR / table_name / f"{table_name}.parquet"

    bronze_table_dir = BRONZE_DIR / table_name
    bronze_table_dir.mkdir(parents=True, exist_ok=True)

    bronze_file = bronze_table_dir / f"{table_name}.parquet"

    print(f"\nProcessing: {table_name}")

    # Read RAW
    df = pd.read_parquet(raw_file)

    # Add ingestion metadata
    df["_ingested_at"] = ingestion_time
    df["_source_system"] = "PostgreSQL_ecommerce"
    df["_batch_id"] = batch_id

    # Write BRONZE
    df.to_parquet(
        bronze_file,
        engine="pyarrow",
        index=False
    )

    print(f"Rows          : {len(df)}")
    print(f"Bronze output : {bronze_file}")


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 60)
    print("RAW → BRONZE PIPELINE")
    print("=" * 60)

    batch_id = str(uuid.uuid4())

    ingestion_time = datetime.now(timezone.utc).isoformat()

    print(f"Batch ID      : {batch_id}")
    print(f"Ingested at   : {ingestion_time}")

    for table in TABLES:

        raw_file = RAW_DIR / table / f"{table}.parquet"

        if not raw_file.exists():
            print(f"❌ Missing RAW file: {raw_file}")
            continue

        process_table(
            table,
            batch_id,
            ingestion_time
        )

    print("\n" + "=" * 60)
    print("RAW → BRONZE COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()
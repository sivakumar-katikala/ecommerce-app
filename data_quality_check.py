from pathlib import Path
import pandas as pd


# ============================================================
# Local Data Lake
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
# Data Quality Functions
# ============================================================

def check_table(table_name):

    file_path = RAW_DIR / table_name / f"{table_name}.parquet"

    print("\n" + "=" * 60)
    print(f"DATA QUALITY CHECK: {table_name}")
    print("=" * 60)

    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False

    df = pd.read_parquet(file_path)

    print(f"Rows       : {len(df)}")
    print(f"Columns    : {len(df.columns)}")
    print(f"Duplicates : {df.duplicated().sum()}")
    print(f"Null values: {df.isnull().sum().sum()}")

    # Empty table check
    if df.empty:
        print("❌ FAILED: Table is empty")
        return False

    # Duplicate check
    duplicate_count = df.duplicated().sum()

    if duplicate_count > 0:
        print(f"⚠️ WARNING: {duplicate_count} duplicate rows found")
    else:
        print("✅ No duplicate rows")

    # Null check
    null_count = df.isnull().sum().sum()

    if null_count > 0:
        print(f"⚠️ WARNING: {null_count} NULL values found")
    else:
        print("✅ No NULL values")

    print("✅ Table validation completed")

    return True


# ============================================================
# Main
# ============================================================

def main():

    print("\n")
    print("*" * 60)
    print("E-COMMERCE DATA QUALITY VALIDATION")
    print("*" * 60)

    successful = 0

    for table in TABLES:

        if check_table(table):
            successful += 1

    print("\n" + "*" * 60)
    print("DATA QUALITY SUMMARY")
    print("*" * 60)

    print(f"Tables checked : {len(TABLES)}")
    print(f"Successful     : {successful}")
    print(f"Failed         : {len(TABLES) - successful}")

    if successful == len(TABLES):
        print("\n✅ ALL TABLES PASSED BASIC VALIDATION")
    else:
        print("\n⚠️ SOME TABLES NEED ATTENTION")


if __name__ == "__main__":
    main()
"""
data_processing.py
====================
Reads production data from a CSV, calculates Material Giveaway figures
for every row, and saves the results -- with three new calculated
columns added -- to a new CSV.

Self-contained: no dependency on financial_calculator.py. Calculations
are done directly with vectorized Pandas operations (faster than
looping row-by-row through a calculator object for a whole dataset).

Input CSV columns expected:
    Timestamp, Product Name, Target Weight, Actual Weight, Cost per Kg

Formulas:
    Weight Drift    = Actual Weight - Target Weight
    Giveaway        = max(0, Weight Drift)   -- underfill floors to 0
    Cost per Packet = (Giveaway / 1000) * Cost per Kg   (Rupees)
    Total Loss      = running cumulative sum of Cost per Packet
                       (last row = grand total loss for the whole dataset)

Output CSV adds:
    Weight Drift, Giveaway, Cost per Packet, Total Loss
"""

import pandas as pd

INPUT_FILE = "production_data.csv"
OUTPUT_FILE = "production_data_processed.csv"


def data_process():
    df = pd.read_csv(INPUT_FILE)

    df["Weight Drift"] = (df["Actual Weight"] - df["Target Weight"]).round(2)
    df["Giveaway"] = df["Weight Drift"].clip(lower=0).round(2)  # underfill -> 0, not negative
    df["Cost per Packet"] = ((df["Giveaway"] / 1000) * df["Cost per Kg"]).round(2)
    df["Total Loss"] = df["Cost per Packet"].cumsum().round(2)  # running total down the rows

    df.to_csv(OUTPUT_FILE, index=False)

    print(f"Processed {len(df)} rows from '{INPUT_FILE}'")
    print(f"Saved results to '{OUTPUT_FILE}'")
    print(f"\nTotal giveaway cost across all rows: Rs {df['Cost per Packet'].sum():.2f}")
    print(f"Rows with giveaway (overfilled):  {(df['Giveaway'] > 0).sum()}")
    print(f"Rows with zero giveaway (on-target or underfilled): {(df['Giveaway'] == 0).sum()}")


if __name__ == "__main__":
    data_process()
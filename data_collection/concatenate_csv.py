#!/usr/bin/env python3
"""Merge all batch CSV files in output/ into output/combined.csv"""

import pandas as pd
import glob
import os


def concatenate_csvs(input_folder: str, output_file: str):
    csv_files = glob.glob(os.path.join(input_folder, "pentest_dataset_batch*.csv"))

    if not csv_files:
        raise ValueError(f"No batch CSV files found in {input_folder}")

    df_list = []
    for file in sorted(csv_files):
        try:
            df = pd.read_csv(file, on_bad_lines='warn')
            df_list.append(df)
            print(f"Read: {os.path.basename(file)} ({len(df)} rows)")
        except Exception as e:
            print(f"Error reading {os.path.basename(file)}: {e}")
            raise

    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.to_csv(output_file, index=False)
    print(f"\nCombined {len(csv_files)} files -> {output_file} ({len(combined_df)} rows)")


if __name__ == "__main__":
    concatenate_csvs("output", "output/combined.csv")

# Data Collection

This folder contains the scripts and helpers used to generate and aggregate the dataset.

## Prerequisites
- Python 3.10+

## Steps
1. Create and activate a virtual environment (venv/conda).
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Review and, if needed, update the machine lists in `machine_lists/`.
4. Generate datasets:
   - `python generate_datasets.py`
5. (Optional) Concatenate outputs into a single CSV:
   - `python concatenate_csv.py`
6. Check results in `output/`.

## Notes
- Example usage is provided in `examples/`.
- Helper utilities are in `dataset_generator_helper.py`.

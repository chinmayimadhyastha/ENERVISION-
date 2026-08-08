# Boosting Regression Project

This project trains and evaluates two boosting regression models on a tabular dataset:

- XGBoost Regressor
- Gradient Boosting Regressor

## Files

- `train_boosting_models.py` - training script
- `requirements.txt` - Python dependencies
- `final_training_dataset (1).csv` - dataset used by the script

## Setup

1. Create and activate a Python environment (recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

From the project folder:

```bash
python train_boosting_models.py
```

If your dataset is stored elsewhere, pass it explicitly:

```bash
python train_boosting_models.py --data /path/to/your/dataset.csv
```

## Output

The script prints:

- RMSE
- MAE
- R²

for both models.

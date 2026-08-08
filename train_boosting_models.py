import argparse
import warnings
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from xgboost import XGBRegressor

warnings.filterwarnings('ignore')


def find_dataset_path(cli_path: str | None) -> Path:
    repo_root = Path(__file__).resolve().parent
    candidates = []
    if cli_path:
        candidates.append(Path(cli_path).expanduser())
    candidates.extend([
        repo_root / 'final_training_dataset (1).csv',
        repo_root / 'final_training_dataset.csv',
        repo_root / 'data' / 'final_training_dataset (1).csv',
        repo_root / 'data' / 'final_training_dataset.csv',
    ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        'Dataset not found. Place the CSV in the repo root or repo/data folder, or pass --data <path>.'
    )


def load_and_preprocess_data(dataset_path: Path):
    df = pd.read_csv(dataset_path)

    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Year'] = df['Date'].dt.year
        df['Month'] = df['Date'].dt.month
        df['Day'] = df['Date'].dt.day
        df['DayOfYear'] = df['Date'].dt.dayofyear
        df.drop(columns=['Date'], inplace=True)

    if df.isna().sum().any():
        for col in df.columns:
            if df[col].dtype.kind in 'fi':
                df[col].fillna(df[col].median(), inplace=True)
            else:
                df[col].fillna(df[col].mode().iloc[0], inplace=True)

    if 'DailyGeneration_MU' not in df.columns:
        raise ValueError('Target column DailyGeneration_MU not found in the dataset.')

    feature_cols = [c for c in df.columns if c != 'DailyGeneration_MU']
    X = df[feature_cols]
    y = df['DailyGeneration_MU'].values

    categorical_cols = X.select_dtypes(include=['object', 'string']).columns.tolist()
    if categorical_cols:
        X = pd.get_dummies(X, columns=categorical_cols, drop_first=False)

    X = X.apply(pd.to_numeric, errors='coerce')
    if X.isna().any().any():
        X = X.fillna(X.median())

    return X, y


def evaluate(model, X_test, y_test, name: str):
    preds = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f'\n{name} Results:')
    print(f'  RMSE: {rmse:.4f}')
    print(f'  MAE : {mae:.4f}')
    print(f'  R2  : {r2:.4f}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Train XGBoost and Gradient Boosting on the provided dataset.')
    parser.add_argument('--data', type=str, default=None, help='Optional path to the dataset CSV file.')
    args = parser.parse_args()

    dataset_path = find_dataset_path(args.data)
    print(f'Loading dataset from: {dataset_path}')

    X, y = load_and_preprocess_data(dataset_path)
    print('Dataset shape:', X.shape[0], 'rows x', X.shape[1], 'features')

    X_train, X_test, y_train, y_test = train_test_split(X.values, y, test_size=0.2, random_state=42)
    print('Train shape:', X_train.shape, 'Test shape:', X_test.shape)

    xgb_param_dist = {
        'n_estimators': [100, 200, 300],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.05, 0.1],
        'subsample': [0.6, 0.8, 1.0],
        'colsample_bytree': [0.6, 0.8, 1.0],
        'reg_alpha': [0, 0.1, 0.5],
        'reg_lambda': [1, 1.5, 2],
    }

    gb_param_dist = {
        'n_estimators': [100, 200, 300],
        'learning_rate': [0.01, 0.05, 0.1],
        'max_depth': [2, 3, 4],
        'subsample': [0.6, 0.8, 1.0],
        'min_samples_split': [2, 4, 6],
        'min_samples_leaf': [1, 2, 4],
    }

    xgb_search = RandomizedSearchCV(
        estimator=XGBRegressor(objective='reg:squarederror', n_jobs=-1, random_state=42, verbosity=0),
        param_distributions=xgb_param_dist,
        n_iter=8,
        scoring='neg_root_mean_squared_error',
        cv=3,
        n_jobs=-1,
        random_state=42,
        verbose=0,
    )

    gb_search = RandomizedSearchCV(
        estimator=GradientBoostingRegressor(random_state=42),
        param_distributions=gb_param_dist,
        n_iter=8,
        scoring='neg_root_mean_squared_error',
        cv=3,
        n_jobs=-1,
        random_state=42,
        verbose=0,
    )

    print('Tuning XGBoost...')
    xgb_search.fit(X_train, y_train)
    print('Tuning Gradient Boosting...')
    gb_search.fit(X_train, y_train)

    best_xgb = xgb_search.best_estimator_
    best_gb = gb_search.best_estimator_

    print('\nBest XGBoost parameters:', xgb_search.best_params_)
    print('Best Gradient Boosting parameters:', gb_search.best_params_)

    evaluate(best_xgb, X_test, y_test, 'Tuned XGBoost')
    evaluate(best_gb, X_test, y_test, 'Tuned Gradient Boosting')

    print('\nTraining complete.')

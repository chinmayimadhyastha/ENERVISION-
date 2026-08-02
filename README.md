# 🌱 EnerVision

## AI-Based Renewable Energy Generation Forecasting for Karnataka

EnerVision is a machine learning project that forecasts **plant-wise renewable energy generation** in Karnataka using historical weather data and official power generation records.

The project integrates **NASA POWER weather data** with **Central Electricity Authority (CEA) plant-wise generation reports** to build a clean machine learning dataset for renewable energy forecasting.

---

# Project Objectives

- Collect official renewable power generation data
- Collect historical weather data using NASA POWER API
- Clean and preprocess multiple datasets
- Merge weather and generation datasets
- Train a Random Forest regression model
- Tune model hyperparameters
- Evaluate model performance
- Generate prediction reports and visualizations

---

# Data Sources

### 1. Central Electricity Authority (CEA)

- Plant-wise Renewable Energy Generation Reports
- Karnataka Renewable Plant Metadata

### 2. NASA POWER API

Historical daily weather parameters:

- Temperature
- Relative Humidity
- Wind Speed
- Global Horizontal Irradiance (GHI)
- Surface Pressure

---

# Final Dataset

| Property | Value |
|----------|------:|
| Records | 3764 |
| Missing Values | 0 |
| Plants | 23 |
| Weather Features | 5 |
| Target | Daily Renewable Generation (MU) |

---

# Features Used

- Temperature
- Humidity
- Wind Speed
- GHI
- Pressure
- Capacity (MW)
- Plant Type
- District
- Month
- Day
- Day Of Year

---

# Target Variable

DailyGeneration_MU

---

# Machine Learning Model

- Random Forest Regressor
- GridSearchCV Hyperparameter Tuning

---

# Model Performance

| Metric | Value |
|---------|-------:|
| MAE | 0.2467 |
| RMSE | 0.5425 |
| R² Score | 0.6796 |

Best Parameters

- Trees: 200
- Max Depth: 10

---

# Project Workflow

```
Plant Metadata
      │
      ▼
Geocoding
      │
      ▼
NASA POWER API
      │
      ▼
Weather Dataset
      │
      ▼
CEA Generation Reports
      │
      ▼
Generation Extraction
      │
      ▼
Data Cleaning
      │
      ▼
Dataset Merge
      │
      ▼
Random Forest Training
      │
      ▼
Generation Prediction
```

---

# Project Structure

```text
EnerVision
│
├── data
│   ├── final
│   ├── generation
│   ├── metadata
│   ├── raw
│   └── weather
│
├── models
│
├── plots
│
├── reports
│
├── scripts
│
├── README.md
└── requirements.txt
```

---

# Generated Outputs

- Final Training Dataset
- Trained Random Forest Model
- Feature Importance Report
- MAE / RMSE / R² Metrics
- Actual vs Predicted Plot
- Residual Plot

---

# Technologies Used

- Python
- Pandas
- NumPy
- Scikit-learn
- Matplotlib
- Joblib
- NASA POWER API
- Central Electricity Authority (CEA)

---

# Future Improvements

- XGBoost Model
- LSTM Time-Series Forecasting
- Real-Time Weather Integration
- Web Dashboard
- Live Renewable Generation Prediction

---

# Developed By

EnerVision Project Team

Phase-II Major Project
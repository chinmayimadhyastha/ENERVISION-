# 🌞 EnerVision

## AI-Powered Solar Irradiance Forecasting for Karnataka

EnerVision is a machine learning project that predicts **Global Horizontal Irradiance (GHI)** across Karnataka using historical weather data collected from NASA POWER. The project serves as the foundation for district-wise renewable energy forecasting and supports future solar energy estimation.

---

## 📌 Project Objectives

- Build a clean Karnataka weather dataset
- Perform data preprocessing and feature engineering
- Train and evaluate a Random Forest regression model
- Analyze feature importance
- Visualize prediction performance
- Provide a reusable dataset for multiple ML models

---

## 🛰 Dataset

**Source:** NASA POWER API

**Coverage:** 31 districts of Karnataka

**Duration:** 2020–2025

**Records:** 67,952

---

## 📊 Features Used

- Temperature (°C)
- Relative Humidity (%)
- Wind Speed (m/s)
- Latitude
- Longitude
- Year
- Month
- Day
- Week
- Day of Year
- Season

---

## 🎯 Target Variable

Global Horizontal Irradiance (GHI)

---

## 🤖 Machine Learning Model

Random Forest Regressor

---

## 📈 Model Performance

| Metric | Value |
|---------|-------|
| MAE | 0.376 |
| RMSE | 0.536 |
| R² Score | 0.8225 |

---

## 📁 Project Structure

```text
EnerVision/
│
├── data/
├── models/
├── notebooks/
├── plots/
├── reports/
├── scripts/
├── README.md
└── requirements.txt
```

---

## 📷 Results

The project generates:

- Correlation Heatmap
- Feature Importance
- Actual vs Predicted Plot
- Residual Plot
- Temperature Distribution
- GHI Boxplot

---

## 🛠 Technologies Used

- Python
- Pandas
- NumPy
- Scikit-learn
- Matplotlib
- Seaborn
- NASA POWER API

---

## 👩‍💻 Developed By

EnerVision Project Team

Phase-2 Major Project
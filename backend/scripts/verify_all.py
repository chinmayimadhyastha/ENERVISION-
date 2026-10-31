"""Comprehensive verification runner for ENERVISION backend.
Executes all verification phases (APIs, Real Data, Models, Preprocessing, DB,
Confidence, Explainability, Horizons, Performance) and records exact outputs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.app_factory import create_app


def run_verification() -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version,
        "results": {},
    }

    print(">>> 1. Creating Flask App and Initializing Container...")
    t0 = time.time()
    app = create_app()
    container = app.extensions["enervision"]
    init_time = time.time() - t0
    report["results"]["startup"] = {
        "status": "SUCCESS",
        "init_time_seconds": round(init_time, 3),
        "database_engine": str(container.db.engine.url) if container.db and container.db.engine else None,
        "models_loaded": list(container.models.models.keys()) if hasattr(container.models, "models") else list(container.models.status().keys()),
        "plants_loaded_count": len(container.data.plants_by_id),
    }
    print(f"Startup OK in {init_time:.2f}s. Models loaded: {report['results']['startup']['models_loaded']}")

    client = app.test_client()

    # >>> 2. Health Check
    print(">>> 2. Verifying Health Check...")
    r_health = client.get("/api/health")
    health_data = r_health.get_json()
    report["results"]["health"] = {
        "status_code": r_health.status_code,
        "data": health_data,
        "pass": r_health.status_code == 200 and health_data.get("status") in ("ok", "healthy"),
    }
    print(f"Health Check: {report['results']['health']['pass']} ({r_health.status_code})")

    # >>> 3. Testing All Endpoints Matrix
    print(">>> 3. Testing All Endpoints Matrix...")
    endpoints_to_test = [
        # (name, method, url, body, expected_code)
        ("Health", "GET", "/api/health", None, 200),
        ("Plants List", "GET", "/api/plants", None, 200),
        ("Plant Valid (kredl)", "GET", "/api/plants/kredl", None, 200),
        ("Plant Invalid", "GET", "/api/plants/NON_EXISTENT_PLANT", None, 404),
        ("Weather List (Valid Plant & Range)", "GET", "/api/weather?plant_id=kredl&start_date=2026-08-01&end_date=2026-08-03", None, 200),
        ("Weather List (Missing plant_id)", "GET", "/api/weather", None, 400),
        ("Weather List (Invalid Date)", "GET", "/api/weather?plant_id=kredl&start_date=not-a-date", None, 400),
        ("Weather Plant (kredl)", "GET", "/api/weather/kredl?start_date=2026-08-01&end_date=2026-08-03", None, 200),
        ("Weather Plant Invalid", "GET", "/api/weather/INVALID_PLANT?start_date=2026-08-01", None, 404),
        ("Generation List", "GET", "/api/generation", None, 200),
        ("Generation Plant (kredl)", "GET", "/api/generation/kredl", None, 200),
        ("Generation Plant Invalid", "GET", "/api/generation/INVALID_PLANT", None, 404),
        ("Generation History", "GET", "/api/generation/history", None, 200),
        ("Forecast GET Valid (Singular)", "GET", "/api/forecast?plant_id=kredl&horizon=3&base_date=2026-08-01", None, 200),
        ("Forecast GET Valid (Plural)", "GET", "/api/forecasts?plant_id=kredl&horizon=3&base_date=2026-08-01", None, 200),
        ("Forecast GET Missing plant_id", "GET", "/api/forecast?horizon=3", None, 400),
        ("Forecast GET Invalid horizon", "GET", "/api/forecast?plant_id=kredl&horizon=999", None, 400),
        ("Forecast GET Invalid plant", "GET", "/api/forecast?plant_id=FAKE_PLANT&horizon=3", None, 404),
        ("Forecast GET Plant ID Path", "GET", "/api/forecast/kredl?horizon=3&base_date=2026-08-01", None, 200),
        ("Forecast POST Valid", "POST", "/api/forecast", {"plant_id": "kredl", "horizon": 3, "base_date": "2026-08-01"}, 200),
        ("Forecast POST Invalid Body", "POST", "/api/forecast", "invalid json", 400),
        ("Forecast POST Missing plant_id", "POST", "/api/forecast", {"horizon": 3}, 400),
        ("Models Registry", "GET", "/api/models", None, 200),
        ("Model Valid (random_forest)", "GET", "/api/models/random_forest", None, 200),
        ("Model Valid (random_forest_daily)", "GET", "/api/models/random_forest_daily", None, 200),
        ("Model Invalid", "GET", "/api/models/non_existent_model", None, 404),
        ("Explainability (kredl)", "GET", "/api/explainability/kredl?base_date=2026-08-01", None, 200),
        ("Explainability Invalid Plant", "GET", "/api/explainability/FAKE_PLANT", None, 404),
    ]

    endpoint_matrix = []
    for name, method, url, body, exp_code in endpoints_to_test:
        t_start = time.time()
        if method == "GET":
            res = client.get(url)
        elif method == "POST":
            if isinstance(body, str):
                res = client.post(url, data=body, content_type="application/json")
            else:
                res = client.post(url, json=body)
        duration_ms = round((time.time() - t_start) * 1000, 2)
        passed = (res.status_code == exp_code)
        endpoint_matrix.append({
            "name": name,
            "method": method,
            "url": url,
            "expected_code": exp_code,
            "actual_code": res.status_code,
            "duration_ms": duration_ms,
            "pass": passed,
        })
        status_symbol = "OK" if passed else "FAIL"
        print(f"  [{status_symbol}] {method} {url} -> {res.status_code} (exp {exp_code}) {duration_ms}ms")

    report["results"]["endpoint_matrix"] = endpoint_matrix

    # >>> 4. Real Plant Data Verification
    print(">>> 4. Verifying Real Plant Data...")
    r_plants = client.get("/api/plants").get_json()
    plants = r_plants.get("plants", [])
    report["results"]["plants"] = {
        "count": len(plants),
        "plants_summary": [
            {
                "id": p.get("id") or p.get("plant_id"),
                "name": p.get("name") or p.get("plant_name"),
                "type": p.get("plant_type") or p.get("type"),
                "capacity_mw": p.get("capacity_mw"),
                "district": p.get("district"),
                "lat": p.get("latitude"),
                "lon": p.get("longitude"),
            }
            for p in plants[:5]
        ],
    }

    # >>> 5. Real Weather Data Verification
    print(">>> 5. Verifying Real Weather Data...")
    r_weather = client.get("/api/weather/kredl?start_date=2026-08-01&end_date=2026-08-03").get_json()
    w_records = r_weather.get("history") or r_weather.get("data") or r_weather.get("weather") or []
    first_w = w_records[0] if (isinstance(w_records, list) and w_records) else r_weather
    report["results"]["weather"] = {
        "plant_id": "kredl",
        "returned_records_count": len(w_records) if isinstance(w_records, list) else 1,
        "first_record": first_w,
    }

    # >>> 6. Real Generation Data Verification
    print(">>> 6. Verifying Real Generation Data...")
    r_gen = client.get("/api/generation/kredl?start_date=2026-08-01&end_date=2026-08-03").get_json()
    gen_records = r_gen.get("history") or r_gen.get("data") or r_gen.get("records") or []
    report["results"]["generation"] = {
        "plant_id": "kredl",
        "sample_count": len(gen_records),
        "first_record": gen_records[0] if gen_records else None,
    }

    # >>> 7. Real ML Model Predictions & Preprocessing Fidelity
    print(">>> 7. Verifying ML Models (Random Forest, Solar LSTM, Wind LSTM)...")
    models_tested = {}
    for model_type, plant_id, base_dt in [
        ("rf", "kredl", "2021-06-01"),
        ("solar_lstm", "kredl", "2026-08-01"),
        ("wind_lstm", "gadag-vena-w", "2026-08-01"),
    ]:
        t_pred0 = time.time()
        url = f"/api/forecast?plant_id={plant_id}&horizon=1&model={model_type}&base_date={base_dt}&include_confidence=true&include_explanation=true"
        r_pred = client.get(url)
        pred_time = round((time.time() - t_pred0) * 1000, 2)
        pred_data = r_pred.get_json()

        forecast_list = pred_data.get("forecasts") or pred_data.get("forecast") or []
        first_entry = forecast_list[0] if forecast_list else {}

        models_tested[model_type] = {
            "status_code": r_pred.status_code,
            "prediction_time_ms": pred_time,
            "plant_id": plant_id,
            "base_date": base_dt,
            "status": pred_data.get("status"),
            "forecast_points": len(forecast_list),
            "sample_prediction": first_entry.get("prediction"),
            "raw_prediction": first_entry.get("raw_prediction"),
            "unit": first_entry.get("unit"),
            "confidence": first_entry.get("confidence"),
            "explanation": first_entry.get("explanation"),
        }
        print(f"  Model {model_type} on {plant_id}: {models_tested[model_type]['sample_prediction']} {models_tested[model_type]['unit']} in {pred_time}ms")

    report["results"]["models_tested"] = models_tested

    # >>> 8. Horizon Scaling Verification
    print(">>> 8. Verifying Forecast Horizons (1, 3, 7 days)...")
    horizons_tested = {}
    for h in [1, 3, 7]:
        r_h = client.get(f"/api/forecast?plant_id=kredl&horizon={h}&base_date=2021-06-01")
        h_data = r_h.get_json()
        forecasts = h_data.get("forecasts") or h_data.get("forecast") or []
        dates = [f.get("date") for f in forecasts]
        horizons_tested[f"horizon_{h}"] = {
            "status_code": r_h.status_code,
            "status": h_data.get("status"),
            "points_returned": len(forecasts),
            "expected_points": h,
            "dates_ordered": dates == sorted(dates),
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
        }
    report["results"]["horizons_tested"] = horizons_tested

    # >>> 9. Database Persistence Verification
    print(">>> 9. Verifying Database Persistence...")
    post_res = client.post("/api/forecast", json={
        "plant_id": "kredl",
        "horizon": 2,
        "base_date": "2021-06-01",
        "model": "random_forest"
    })
    post_json = post_res.get_json()

    # Query DB directly to check stored forecast record
    from backend.db.models import PlantModel, ForecastRecordModel, ModelRegistryModel
    db_session = container.db.session_factory()
    try:
        db_plants_count = db_session.query(PlantModel).count()
        db_models_count = db_session.query(ModelRegistryModel).count()
        db_forecasts_count = db_session.query(ForecastRecordModel).count()
        latest_fc = db_session.query(ForecastRecordModel).order_by(ForecastRecordModel.created_at.desc()).first()

        report["results"]["database"] = {
            "plants_in_db": db_plants_count,
            "models_in_db": db_models_count,
            "forecast_records_in_db": db_forecasts_count,
            "latest_stored_forecast": {
                "id": latest_fc.id if latest_fc else None,
                "plant_id": latest_fc.plant_id if latest_fc else None,
                "model_id": latest_fc.model_id if latest_fc else None,
                "horizon": latest_fc.horizon_days if latest_fc else None,
                "items_count": len(latest_fc.predictions) if latest_fc else 0,
            }
        }
        print(f"DB check: {db_plants_count} plants, {db_models_count} models, {db_forecasts_count} forecast runs stored.")
    finally:
        db_session.close()

    # >>> 10. Model Metrics Verification
    print(">>> 10. Verifying Model Metrics...")
    r_models = client.get("/api/models").get_json()
    model_list = r_models.get("models") or []
    report["results"]["metrics"] = {
        m.get("model_id") or m.get("id"): {
            "name": m.get("name"),
            "target": m.get("target_variable"),
            "metrics": m.get("metrics"),
        }
        for m in model_list
    }

    # Summary
    all_endpoints_pass = all(item["pass"] for item in endpoint_matrix)
    report["results"]["summary"] = {
        "all_endpoints_pass": all_endpoints_pass,
        "total_endpoints_tested": len(endpoint_matrix),
        "failed_endpoints_count": sum(1 for item in endpoint_matrix if not item["pass"]),
    }

    return report


if __name__ == "__main__":
    report = run_verification()
    output_path = os.path.join(REPO_ROOT, "docs", "BACKEND_VERIFICATION_RESULTS.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nVerification finished successfully. Detailed results written to {output_path}")

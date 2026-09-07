from __future__ import annotations
import json
import os
from typing import Optional, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="HFT & Volatility Dispersion Arbitrage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKTEST_PATH = os.getenv("HFT_RESULTS_PATH", "results/backtest_report.json")
DISPERSION_PATH = os.getenv("DISPERSION_RESULTS_PATH", "results/dispersion_report.json")

def load_json(filepath: str) -> dict[str, Any]:
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/results")
def get_results():
    return load_json(BACKTEST_PATH)

@app.get("/api/dispersion")
def get_dispersion():
    return load_json(DISPERSION_PATH)

@app.get("/api/groww/status")
def get_groww_status():
    try:
        from data.groww_adapter import GrowwAdapter
        adapter = GrowwAdapter()
        if adapter.connect():
            profile = adapter.get_profile() or {}
            return {
                "connected": True,
                "ucc": profile.get("ucc", "8640362185"),
                "vendor_user_id": profile.get("vendor_user_id", ""),
                "nse_enabled": profile.get("nse_enabled", True),
                "bse_enabled": profile.get("bse_enabled", True),
                "active_segments": profile.get("active_segments", ["CASH"]),
                "feed_ready": True
            }
        return {"connected": False, "error": "Could not authenticate"}
    except Exception as e:
        return {"connected": False, "error": str(e)}

@app.get("/api/groww/holdings")
def get_groww_holdings():
    try:
        from data.groww_adapter import GrowwAdapter
        adapter = GrowwAdapter()
        if adapter.connect():
            return adapter.get_holdings() or {"holdings": []}
        return {"holdings": []}
    except Exception as e:
        return {"error": str(e), "holdings": []}

@app.get("/api/groww/positions")
def get_groww_positions():
    try:
        from data.groww_adapter import GrowwAdapter
        adapter = GrowwAdapter()
        if adapter.connect():
            return adapter.get_positions() or {"positions": []}
        return {"positions": []}
    except Exception as e:
        return {"error": str(e), "positions": []}

# Mount static dashboard files
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

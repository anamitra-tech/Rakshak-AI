"""
Standalone investigator-facing Fraud Network Graph + Geospatial Intelligence
dashboard. Separate FastAPI process/port from api.server (8000) and
webhook.app (8001) -- not a citizen-facing surface, no changes to either of
those apps or to ml/detector.py, casefile/case_generator.py, or
graph/fraud_graph.py.

Serves both the bundled browser UI (/, /dashboard/data) and a clean typed
REST API for external integration under /api/v1 -- see dashboard/api.py and
dashboard/API.md, or the auto-generated docs at /docs once running.

Run:
    uvicorn dashboard.investigator_app:app --port 8002

Then open http://127.0.0.1:8002/ in a browser, or http://127.0.0.1:8002/docs
for the interactive API reference.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

from dashboard.api import router as api_router
from dashboard.data_provider import get_graph
from dashboard.telecom_circles import CIRCLE_CENTROIDS, UNKNOWN_CIRCLE

app = FastAPI(title="Rakshak Investigator Dashboard (demo)")
app.include_router(api_router)

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
def index():
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/dashboard/data")
def dashboard_data():
    """Aggregate payload for the bundled browser UI only. External
    integrations should use /api/v1/* (dashboard/API.md) instead -- this
    endpoint's shape is tied to static/index.html and may change with it."""
    graph = get_graph()
    circle_points = []
    for node in graph["nodes"]:
        circle = node["telecom_circle"]
        if circle == UNKNOWN_CIRCLE or circle not in CIRCLE_CENTROIDS:
            continue
        lat, lng = CIRCLE_CENTROIDS[circle]
        circle_points.append({
            "circle": circle,
            "lat": lat,
            "lng": lng,
            "node_id": node["node_id"],
            "cluster_id": node["cluster_id"],
            "risk_level": node["risk_level"],
            "source": node["source"],
        })

    return JSONResponse({
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "clusters": graph["clusters"],
        "circle_points": circle_points,
        "meta": {
            "total_nodes": len(graph["nodes"]),
            "data_scale_note": (
                "Demo-scale seed data only (feedback.db real corrections + "
                "rakshak_eval_testset.json scored through the live detector) "
                "-- not live production complaint volume."
            ),
            "location_disclaimer": (
                "Map points show where reports/telecom-circle allocation "
                "indicate a NUMBER was registered, not where a scammer is "
                "physically located -- precise perpetrator geolocation "
                "requires telecom-carrier access this system does not have."
            ),
        },
    })

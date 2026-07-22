"""
MODULE 4 — Geo Fraud Intelligence Layer.

Grid-bucketing hotspot detection over fraud complaint coordinates (no heavy
deps; DBSCAN-style density via grid). Emits heatmap cells + ranked hotspots
for a command-centre map.
"""
from collections import defaultdict
import math


class GeoFraudLayer:
    def __init__(self, cell_deg=0.05):
        self.points = []          # list of (lat, lng, weight, meta)
        self.cell = cell_deg      # ~5.5 km grid at Indian latitudes

    def add(self, lat, lng, weight=1, meta=None):
        self.points.append((float(lat), float(lng), float(weight), meta or {}))

    def bulk_add(self, pts):
        for p in pts:
            self.add(p["lat"], p["lng"], p.get("weight", 1), p.get("meta"))

    def analyze(self, top_k=5):
        buckets = defaultdict(lambda: {"count": 0, "weight": 0.0, "lat": 0.0, "lng": 0.0})
        for lat, lng, w, _ in self.points:
            key = (round(lat / self.cell), round(lng / self.cell))
            b = buckets[key]
            b["count"] += 1
            b["weight"] += w
            b["lat"] += lat
            b["lng"] += lng

        cells = []
        for (gx, gy), b in buckets.items():
            cells.append({
                "lat": round(b["lat"] / b["count"], 4),
                "lng": round(b["lng"] / b["count"], 4),
                "count": b["count"],
                "intensity": round(b["weight"], 2),
            })
        max_w = max((c["intensity"] for c in cells), default=1)
        for c in cells:
            c["normalized"] = round(c["intensity"] / max_w, 3)

        hotspots = sorted(cells, key=lambda c: c["intensity"], reverse=True)[:top_k]
        for i, h in enumerate(hotspots):
            h["rank"] = i + 1
            h["priority"] = "CRITICAL" if h["normalized"] > 0.7 else \
                            "HIGH" if h["normalized"] > 0.4 else "MEDIUM"

        return {"heatmap": cells, "hotspots": hotspots,
                "total_reports": len(self.points), "cells": len(cells)}


def demo_points(seed=3):
    """Synthetic complaints clustered around Indian metros."""
    import random
    random.seed(seed)
    centers = {"Delhi": (28.61, 77.21, 40), "Mumbai": (19.07, 72.87, 25),
               "Jamtara": (23.95, 86.80, 30), "Bengaluru": (12.97, 77.59, 15),
               "Kolkata": (22.57, 88.36, 10)}
    pts = []
    for _, (lat, lng, n) in centers.items():
        for _ in range(n):
            pts.append({"lat": lat + random.gauss(0, 0.08),
                        "lng": lng + random.gauss(0, 0.08),
                        "weight": random.choice([1, 1, 1, 2, 3])})
    return pts


if __name__ == "__main__":
    g = GeoFraudLayer()
    g.bulk_add(demo_points())
    r = g.analyze()
    print(f"reports={r['total_reports']} cells={r['cells']}")
    for h in r["hotspots"]:
        print(f"  #{h['rank']} {h['priority']:8s} ({h['lat']},{h['lng']}) count={h['count']} intensity={h['intensity']}")

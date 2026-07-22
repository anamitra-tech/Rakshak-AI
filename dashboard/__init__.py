"""
Investigator-facing Fraud Network Graph + Geospatial Intelligence dashboard.

Standalone from the citizen Android app and from api.server/webhook.app's
production request paths — this package only *reads* ml.detector's output
(via ScamDetector.predict(), never modifying it) and the existing
feedback/data/feedback.db SQLite file. Nothing here is imported by, or
imports into, the citizen-facing detection pipeline.
"""

// Shared constants for the Geospatial Crime Intelligence module.

// Fallback list -- the real source of truth is GET /api/geo/scam-types
// (Backend/app/services/geo_service.py SCAM_TYPES). Used only until that
// request resolves, so the filter panel isn't empty on first paint.
export const FALLBACK_SCAM_TYPES = [
  'UPI Fraud',
  'Phishing',
  'Investment Scam',
  'Loan App Fraud',
  'KYC Fraud',
  'Job Fraud',
  'Digital Arrest',
];

export const SCAM_TYPE_COLORS = {
  'UPI Fraud': '#22d3ee',
  'Phishing': '#a78bfa',
  'Investment Scam': '#f59e0b',
  'Loan App Fraud': '#fb7185',
  'KYC Fraud': '#34d399',
  'Job Fraud': '#818cf8',
  'Digital Arrest': '#ef4444',
};

export const DATE_PRESETS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
];

// No API-key/token dark basemap: CARTO's free "dark_all" raster tiles,
// wrapped as an inline MapLibre style (avoids needing a Mapbox account).
export const DARK_MAP_STYLE = {
  version: 8,
  sources: {
    'carto-dark': {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        'https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors © CARTO',
    },
  },
  layers: [
    {
      id: 'carto-dark-layer',
      type: 'raster',
      source: 'carto-dark',
      minzoom: 0,
      maxzoom: 20,
    },
  ],
};

export const INDIA_VIEW = {
  longitude: 78.9629,
  latitude: 22.5937,
  zoom: 4.2,
};

// Risk score (0-100) -> color, low to high.
export const riskColor = (score) => {
  if (score >= 66) return '#ef4444'; // high
  if (score >= 33) return '#f59e0b'; // medium
  return '#22c55e'; // low
};

export const riskLabel = (score) => {
  if (score >= 66) return 'High';
  if (score >= 33) return 'Medium';
  return 'Low';
};

export const trendColor = (trend) =>
  trend === 'up' ? '#ef4444' : trend === 'down' ? '#34d399' : '#94a3b8';

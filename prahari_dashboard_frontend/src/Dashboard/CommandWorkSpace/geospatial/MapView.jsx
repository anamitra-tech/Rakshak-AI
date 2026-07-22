// src/Dashboard/CommandWorkSpace/geospatial/MapView.jsx
import { useCallback, useMemo, useRef, useState } from 'react';
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { DARK_MAP_STYLE, INDIA_VIEW, SCAM_TYPE_COLORS } from './constants';

const LAYER_CLUSTERS = 'clusters';
const LAYER_CLUSTER_COUNT = 'cluster-count';
const LAYER_POINTS = 'unclustered-point';
const LAYER_HEATMAP = 'complaints-heatmap';
const LAYER_DISTRICT_FILL = 'district-fill';
const LAYER_DISTRICT_LINE = 'district-line';

const complaintsToGeoJSON = (complaints) => ({
  type: 'FeatureCollection',
  features: complaints.map((c, i) => ({
    type: 'Feature',
    id: i,
    geometry: { type: 'Point', coordinates: [c.lng, c.lat] },
    properties: {
      scam_type: c.scam_type,
      amount: c.amount,
      risk_score: c.risk_score,
      date: c.date,
      district: c.district,
    },
  })),
});

const buildDistrictsGeoJSON = (rawFeatures, statsById) => ({
  type: 'FeatureCollection',
  features: rawFeatures.map((f) => {
    const stat = statsById[f.properties.district];
    return {
      ...f,
      properties: {
        ...f.properties,
        has_data: !!stat,
        risk_score: stat ? stat.risk_score : -1,
        complaint_count: stat ? stat.complaint_count : 0,
        top_scam_type: stat ? stat.top_scam_type : null,
        trend: stat ? stat.trend : null,
        trend_delta_pct: stat ? stat.trend_delta_pct : null,
      },
    };
  }),
});

const MapView = ({
  complaints,
  districtStats,
  districtsRaw,
  viewMode,
  showChoropleth,
  onSelectDistrict,
}) => {
  const mapRef = useRef(null);
  const [popup, setPopup] = useState(null);
  const [hoveredDistrict, setHoveredDistrict] = useState(null);

  const pointsGeoJSON = useMemo(() => complaintsToGeoJSON(complaints), [complaints]);

  const statsById = useMemo(() => {
    const map = {};
    for (const s of districtStats) map[s.district_id] = s;
    return map;
  }, [districtStats]);

  const districtsGeoJSON = useMemo(
    () => (districtsRaw ? buildDistrictsGeoJSON(districtsRaw.features, statsById) : null),
    [districtsRaw, statsById]
  );

  const interactiveLayerIds = useMemo(() => {
    const ids = [];
    if (viewMode === 'points') ids.push(LAYER_CLUSTERS, LAYER_POINTS);
    if (showChoropleth) ids.push(LAYER_DISTRICT_FILL);
    return ids;
  }, [viewMode, showChoropleth]);

  const getMap = () => mapRef.current?.getMap?.() ?? mapRef.current;

  const handleClick = useCallback((e) => {
    const feature = e.features?.[0];
    if (!feature) return;

    if (feature.layer.id === LAYER_CLUSTERS) {
      const map = getMap();
      const source = map?.getSource('complaints');
      const clusterId = feature.properties.cluster_id;
      source?.getClusterExpansionZoom(clusterId, (err, zoom) => {
        if (err) return;
        map.easeTo({
          center: feature.geometry.coordinates,
          zoom,
          duration: 500,
        });
      });
      return;
    }

    if (feature.layer.id === LAYER_POINTS) {
      setPopup({
        lngLat: feature.geometry.coordinates,
        properties: feature.properties,
      });
      return;
    }

    if (feature.layer.id === LAYER_DISTRICT_FILL) {
      onSelectDistrict?.(feature.properties.district);
    }
  }, [onSelectDistrict]);

  const handleMouseMove = useCallback((e) => {
    const feature = e.features?.find((f) => f.layer.id === LAYER_DISTRICT_FILL);
    if (feature) {
      setHoveredDistrict({
        x: e.point.x,
        y: e.point.y,
        name: feature.properties.district,
        state: feature.properties.state,
        riskScore: feature.properties.risk_score,
        complaintCount: feature.properties.complaint_count,
        topScamType: feature.properties.top_scam_type,
        trend: feature.properties.trend,
      });
    } else {
      setHoveredDistrict(null);
    }
  }, []);

  return (
    <div className="relative h-full w-full overflow-hidden rounded-2xl border border-cyan-400/30 shadow-[0_0_20px_rgba(34,211,238,0.1)]">
      <Map
        ref={mapRef}
        initialViewState={INDIA_VIEW}
        mapStyle={DARK_MAP_STYLE}
        interactiveLayerIds={interactiveLayerIds}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredDistrict(null)}
        cursor={hoveredDistrict ? 'pointer' : 'grab'}
      >
        <NavigationControl position="top-right" />

        {showChoropleth && districtsGeoJSON && (
          <Source id="districts" type="geojson" data={districtsGeoJSON}>
            <Layer
              id={LAYER_DISTRICT_FILL}
              type="fill"
              paint={{
                'fill-color': [
                  'case',
                  ['==', ['get', 'has_data'], false],
                  'rgba(255,255,255,0.02)', // Minimal opacity for unpopulated sectors
                  [
                    'interpolate',
                    ['linear'],
                    ['get', 'risk_score'],
                    0, '#4ade80',    // Vibrant Emerald Green
                    33, '#fbbf24',   // Bright Amber Yellow
                    66, '#f87171',   // High Alert Light Red
                    100, '#dc2626',  // Pure Red Alert Core
                  ],
                ],
                'fill-opacity': [
                  'case',
                  ['==', ['get', 'has_data'], false], 0.1,
                  0.75, // Increased fill saturation for visibility
                ],
              }}
            />
            <Layer
              id={LAYER_DISTRICT_LINE}
              type="line"
              paint={{
                'line-color': 'rgba(34,211,238,0.55)', // Crisper cyan border lines
                'line-width': 0.75,
              }}
            />
          </Source>
        )}

        <Source
          id="complaints"
          type="geojson"
          data={pointsGeoJSON}
          cluster={viewMode === 'points'}
          clusterMaxZoom={12}
          clusterRadius={50}
          clusterProperties={{
            maxRisk: ['max', ['get', 'risk_score']],
          }}
        >
          {viewMode === 'heatmap' && (
            <Layer
              id={LAYER_HEATMAP}
              type="heatmap"
              maxzoom={9}
              paint={{
                'heatmap-weight': [
                  'interpolate', ['linear'], ['get', 'risk_score'],
                  0, 0.1,
                  100, 1,
                ],
                'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1.5, 9, 4],
                'heatmap-color': [
                  'interpolate', ['linear'], ['heatmap-density'],
                  0, 'rgba(0,0,0,0)',
                  0.15, 'rgba(34,211,238,0.2)', // Glowing outer radius halo
                  0.4, '#22d3ee',                // Electric Cyan
                  0.65, '#fbbf24',               // High Contrast Amber
                  0.85, '#f87171',               // Intense Crimson
                  1, '#ffffff',                  // Incandescent White Core
                ],
                'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 8, 9, 32],
                'heatmap-opacity': 0.9,
              }}
            />
          )}

          {viewMode === 'points' && (
            <Layer
              id={LAYER_CLUSTERS}
              type="circle"
              filter={['has', 'point_count']}
              paint={{
                'circle-color': [
                  'step', ['get', 'point_count'],
                  '#4ade80', 10,
                  '#fbbf24', 30,
                  '#f87171',
                ],
                'circle-radius': ['step', ['get', 'point_count'], 16, 10, 20, 30, 26],
                'circle-stroke-width': 3,
                'circle-stroke-color': '#03151A',
              }}
            />
          )}
          {viewMode === 'points' && (
            <Layer
              id={LAYER_CLUSTER_COUNT}
              type="symbol"
              filter={['has', 'point_count']}
              layout={{
                'text-field': ['get', 'point_count_abbreviated'],
                'text-size': 13,
                'text-font': ['DIN Offc Pro Bold', 'Arial Unicode MS Bold'],
              }}
              paint={{ 'text-color': '#03151A' }}
            />
          )}
          {viewMode === 'points' && (
            <Layer
              id={LAYER_POINTS}
              type="circle"
              filter={['!', ['has', 'point_count']]}
              paint={{
                'circle-color': [
                  'match', ['get', 'scam_type'],
                  ...Object.entries(SCAM_TYPE_COLORS).flat(),
                  '#22d3ee',
                ],
                'circle-radius': 6,
                'circle-stroke-width': 1.5,
                'circle-stroke-color': '#03151A',
              }}
            />
          )}
        </Source>

        {popup && (
          <Popup
            longitude={popup.lngLat[0]}
            latitude={popup.lngLat[1]}
            onClose={() => setPopup(null)}
            closeOnClick={false}
            anchor="bottom"
            className="custom-map-popup"
          >
            <div className="text-xs font-mono bg-[#092930]/95 backdrop-blur-md border border-cyan-400/30 text-cyan-100 p-2.5 rounded-xl space-y-1 min-w-[160px] shadow-xl">
              <div className="font-bold border-b border-cyan-500/20 pb-1 text-cyan-300 uppercase tracking-wide">
                {popup.properties.scam_type}
              </div>
              <div className="text-sm font-bold text-white mt-1">
                ₹{Number(popup.properties.amount).toLocaleString('en-IN')}
              </div>
              <div className="text-[10px] text-slate-300 uppercase tracking-wider">{popup.properties.district}</div>
              <div className="text-[10px] text-cyan-400/60 font-medium">{popup.properties.date}</div>
            </div>
          </Popup>
        )}
      </Map>

      {/* High Visibility Floating Tooltip Overlay */}
      {hoveredDistrict && (
        <div
          className="pointer-events-none absolute z-20 rounded-xl border border-cyan-400/40 bg-[#062025]/95 backdrop-blur-md px-3.5 py-3 text-xs font-mono text-slate-200 shadow-2xl min-w-[180px] space-y-1.5"
          style={{ left: hoveredDistrict.x + 16, top: hoveredDistrict.y + 16 }}
        >
          <div className="font-bold text-sm tracking-wide text-cyan-300 uppercase border-b border-cyan-500/20 pb-1">
            {hoveredDistrict.name}
          </div>
          <div className="text-[10px] text-slate-400 font-sans tracking-normal">{hoveredDistrict.state}</div>
          
          {hoveredDistrict.riskScore >= 0 ? (
            <div className="space-y-1 pt-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-slate-400">INCIDENTS:</span>
                <span className="font-bold text-white">{hoveredDistrict.complaintCount}</span>
              </div>
              <div className="flex justify-between gap-3">
                <span className="text-slate-400">PRIMARY:</span>
                <span className="font-bold text-amber-300 max-w-[100px] truncate text-right">{hoveredDistrict.topScamType}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">TRENDLINE:</span>
                <span className="font-bold text-cyan-300 uppercase">{hoveredDistrict.trend}</span>
              </div>
            </div>
          ) : (
            <div className="pt-1 text-[10px] text-slate-500 uppercase tracking-wider italic">No Active Threats Logged</div>
          )}
        </div>
      )}
    </div>
  );
};

export default MapView;
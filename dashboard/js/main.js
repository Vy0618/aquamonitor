import { fetchStations } from "./api.js";
import { HEATMAP_CONFIG } from "./config.js";
import { filterStations, initializeFilterEvents, initializeFilters } from "./filters.js";
import { createHeatmap, updateHeatmap, initializeMapEvents, updateMap } from "./heatmap.js";
import { createMap } from "./map.js";
import { createMarkerLayer, updateMarkers } from "./markers.js";
import { startUptime } from "./uptime.js";
import { createZoomIndicator, updateZoomIndicator } from "./zoom.js";
import { fetchDetectionSummary } from "./detection-counter.js";

let selectedStationId = null;
let detectionPollingInterval = null;

async function initializeMap() {
    const map = createMap();
    const markerLayer = createMarkerLayer();
    const zoomDisplay = createZoomIndicator(map);
    startUptime();

    try {
        const stations = await fetchStations();
        initializeFilters(stations);
        const heat = createHeatmap(map, stations, HEATMAP_CONFIG);

        function updateStationMetrics(stationId, summary) {
            const station = stations.find(item => item.station_id === stationId);
            if (!station) return;
            station.detection_summary = {
                total: Number(summary.total || 0),
                by_type: summary.by_type || {},
                timestamp: summary.timestamp || null
            };
            station.detections = station.detection_summary.total;
        }

        const updateVisualization = () => updateMap({
            map, heat, markerLayer, stations, filterStations,
            onStationSelect: selectStation, selectedStationId, config: HEATMAP_CONFIG
        });

        function selectStation(stationId) {
            selectedStationId = stationId;
            const station = stations.find(item => item.station_id === stationId);
            if (station) {
                updateDetectionDisplay(station.detection_summary, station.detection_summary?.timestamp ? "online" : "no-data");
            }
            startDetectionPolling(stationId, updateStationMetrics, updateVisualization);
        }

        initializeFilterEvents(stations, updateVisualization);
        updateMarkers(map, markerLayer, stations, selectStation, selectedStationId);
        initializeMapEvents(map, () => updateHeatmap(map, heat, filterStations(stations), HEATMAP_CONFIG), () => updateZoomIndicator(map, zoomDisplay));
        updateVisualization();
        if (stations.length > 0) selectStation(stations[0].station_id);
        else updateDetectionDisplay(null, "no-data");
    } catch (error) {
        console.error("Error initializing map:", error);
    }
}

function startDetectionPolling(stationId, updateStationMetrics, updateVisualization) {
    if (detectionPollingInterval) clearInterval(detectionPollingInterval);
    const statusEl = document.getElementById("detectionStatus");
    if (statusEl) statusEl.textContent = `polling station ${stationId}...`;

    const pollDetections = async () => {
        try {
            const data = await fetchDetectionSummary(stationId);
            updateStationMetrics(stationId, data);
            if (selectedStationId === stationId) updateDetectionDisplay(data, data.timestamp ? "online" : "no-data");
            updateVisualization();
        } catch (error) {
            console.error("Failed to fetch detection summary:", error);
            if (statusEl) statusEl.textContent = "polling error";
        }
    };
    pollDetections();
    detectionPollingInterval = setInterval(pollDetections, 3000);
}

function updateDetectionDisplay(data, state = "loading") {
    const countEl = document.getElementById("detectionCount");
    const typesEl = document.getElementById("detectionTypes");
    const statusEl = document.getElementById("detectionStatus");
    const valueSpan = countEl?.querySelector(".count-value");
    if (valueSpan) valueSpan.textContent = data?.total || 0;
    if (typesEl) {
        const entries = Object.entries(data?.by_type || {});
        typesEl.textContent = entries.length ? entries.map(([type, count]) => `${type}: ${count}`).join(" · ") : "no detections";
    }
    if (!statusEl) return;
    if (state === "no-data") statusEl.textContent = "no data";
    else if (state === "loading") statusEl.textContent = "loading";
    else statusEl.textContent = data?.timestamp ? `last detection: ${new Date(data.timestamp).toLocaleTimeString()}` : "online";
}

initializeMap();

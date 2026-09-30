import { detectionTypeLabel } from "./labels.js";
import { fetchStations } from "./api.js";
import { HEATMAP_CONFIG } from "./config.js";
import { clearFilters, filterStations, initializeFilterEvents, initializeFilters } from "./filters.js";
import { createHeatmap, initializeMapEvents, updateMap } from "./heatmap.js";
import { createMap, fitMapToStations } from "./map.js";
import { createMarkerLayer, updateMarkers } from "./markers.js";
import { startUptime } from "./uptime.js";
import { createZoomIndicator, updateZoomIndicator } from "./zoom.js";
import { fetchDetectionSummary } from "./detection-counter.js";
import { initializeStationSearch } from "./station-search.js";
import { updateCityRanking } from "./city-ranking.js";

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
        updateCityRanking(stations);
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
            updateCityRanking(stations);
        }

        const updateVisualization = () => updateMap({
            map, heat, markerLayer, stations, filterStations,
            onStationSelect: selectStation, selectedStationId, config: HEATMAP_CONFIG
        });

        function selectStation(stationId) {
            selectedStationId = stationId;
            document.getElementById("selectedStation").textContent = `Estação #${stationId}`;
            const station = stations.find(item => item.station_id === stationId);
            if (station) {
                updateDetectionDisplay(station.detection_summary, station.detection_summary?.timestamp ? "online" : "no-data");
            }
            startDetectionPolling(stationId, updateStationMetrics, updateVisualization);
        }

        initializeFilterEvents(stations, updateVisualization, filteredStations => {
            fitMapToStations(map, filteredStations);
        });
        initializeStationSearch(stations, station => {
            if (!filterStations(stations).includes(station)) {
                clearFilters(stations, updateVisualization);
            }
            selectStation(station.station_id);
            const [longitude, latitude] = station.location.coordinates;
            map.setView([Number(latitude), Number(longitude)],
                Math.max(map.getZoom(), 16, HEATMAP_CONFIG.markers.minZoom));
            updateVisualization();
        });
        updateMarkers(map, markerLayer, stations, selectStation, selectedStationId);
        initializeMapEvents(map, updateVisualization, () => updateZoomIndicator(map, zoomDisplay));
        updateVisualization();
        if (stations.length > 0) selectStation(stations[0].station_id);
        else updateDetectionDisplay(null, "no-data");
    } catch (error) {
        document.getElementById("cityRankingStatus").textContent = "Não foi possível carregar a classificação.";
        document.getElementById("stationSearchStatus").textContent =
            "Não foi possível carregar as estações. Recarregue a página para tentar novamente.";
        console.error("Error initializing map:", error);
    }
}

function startDetectionPolling(stationId, updateStationMetrics, updateVisualization) {
    if (detectionPollingInterval) clearInterval(detectionPollingInterval);
    const statusEl = document.getElementById("detectionStatus");
    if (statusEl) statusEl.textContent = `Consultando estação ${stationId}...`;

    const pollDetections = async () => {
        try {
            const data = await fetchDetectionSummary(stationId);
            updateStationMetrics(stationId, data);
            if (selectedStationId === stationId) updateDetectionDisplay(data, data.timestamp ? "online" : "no-data");
            updateVisualization();
        } catch (error) {
            console.error("Failed to fetch detection summary:", error);
            if (statusEl && selectedStationId === stationId) statusEl.textContent = "Erro ao atualizar detecções";
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
    if (valueSpan) valueSpan.textContent = Number(data?.total || 0).toLocaleString("pt-BR");
    if (typesEl) {
        const entries = Object.entries(data?.by_type || {});
        typesEl.textContent = entries.length ? entries.map(([type, count]) => `${detectionTypeLabel(type)}: ${Number(count).toLocaleString("pt-BR")}`).join(" · ") : "Nenhuma detecção";
    }
    if (!statusEl) return;
    if (state === "no-data") statusEl.textContent = "Sem dados";
    else if (state === "loading") statusEl.textContent = "Carregando...";
    else statusEl.textContent = data?.timestamp ? `Última detecção: ${new Date(data.timestamp).toLocaleString("pt-BR")}` : "Ativo";
}

initializeMap();

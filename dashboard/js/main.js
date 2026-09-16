import { fetchStations } from "./api.js";
import { HEATMAP_CONFIG } from "./config.js";
import {
    filterStations,
    initializeFilterEvents,
    initializeFilters
} from "./filters.js";
import {
    createHeatmap,
    updateHeatmap,
    initializeMapEvents,
    updateMap
} from "./heatmap.js";
import { createMap } from "./map.js";
import { createMarkerLayer, updateMarkers } from "./markers.js";
import { startUptime } from "./uptime.js";
import { createZoomIndicator, updateZoomIndicator } from "./zoom.js";
import { fetchBottleCount } from "./bottle-counter.js";

let selectedStationId = null;
let bottlePollingInterval = null;

async function initializeMap() {
    const map = createMap();
    const markerLayer = createMarkerLayer();
    const zoomDisplay = createZoomIndicator(map);

    startUptime();

    try {
        const stations = await fetchStations();

        console.log("ESTAÇÕES RECEBIDAS:", stations);
        console.log(
            "LOCALIDADES:",
            stations.map(station => station.administrative)
        );
        console.log(
            "CIDADES:",
            stations.map(station => station.administrative?.city)
        );
        console.log("Stations loaded:", stations.length);

        initializeFilters(stations);

        const heat = createHeatmap(map, stations, HEATMAP_CONFIG);

        function updateStationMetrics(stationId, metrics) {
            const station = stations.find(item => item.station_id === stationId);
            if (!station) {
                return;
            }

            station.bottle_count = {
                count: Number(metrics.count || 0),
                positive: Number(metrics.count_by_direction?.positive || 0),
                negative: Number(metrics.count_by_direction?.negative || 0),
                timestamp: metrics.timestamp || null
            };
            station.detections = station.bottle_count.count;
        }

        function selectStation(stationId) {
            selectedStationId = stationId;
            const station = stations.find(item => item.station_id === stationId);
            if (station) {
                updateBottleCountDisplay(
                    station.bottle_count,
                    station.bottle_count?.timestamp ? "online" : "no-data"
                );
            }
            startBottlePolling(stationId, updateStationMetrics, updateVisualization);
        }

        const updateVisualization = () => {
            updateMap({
                map,
                heat,
                markerLayer,
                stations,
                filterStations,
                onStationSelect: selectStation,
                selectedStationId,
                config: HEATMAP_CONFIG
            });
        };

        initializeFilterEvents(stations, updateVisualization);
        updateMarkers(map, markerLayer, stations, selectStation, selectedStationId);

        initializeMapEvents(
            map,
            () => updateHeatmap(map, heat, filterStations(stations), HEATMAP_CONFIG),
            () => updateZoomIndicator(map, zoomDisplay)
        );

        updateVisualization();

        if (stations.length > 0) {
            selectStation(stations[0].station_id);
        } else {
            updateBottleCountDisplay(null, "no-data");
        }

        console.log("AquaDetector initialized successfully.");
    } catch (error) {
        console.error("Error initializing map:", error);
    }
}

function startBottlePolling(stationId, updateStationMetrics, updateVisualization) {
    if (bottlePollingInterval) {
        clearInterval(bottlePollingInterval);
    }

    const statusEl = document.getElementById("bottleStatus");
    if (statusEl) {
        statusEl.textContent = `polling station ${stationId}...`;
    }

    const pollBottleCount = async () => {
        try {
            const data = await fetchBottleCount(stationId);
            updateStationMetrics(stationId, data);
            if (selectedStationId === stationId) {
                updateBottleCountDisplay(data, data.timestamp ? "online" : "no-data");
            }
            updateVisualization();
        } catch (error) {
            console.error("Failed to fetch bottle count:", error);
            if (statusEl) {
                statusEl.textContent = "polling error";
            }
        }
    };

    pollBottleCount();
    bottlePollingInterval = setInterval(pollBottleCount, 3000);
}

function updateBottleCountDisplay(data, state = "loading") {
    const countEl = document.getElementById("bottleCount");
    const directionPositive = document.getElementById("directionPositive");
    const directionNegative = document.getElementById("directionNegative");
    const statusEl = document.getElementById("bottleStatus");

    if (countEl) {
        const valueSpan = countEl.querySelector(".count-value");
        if (valueSpan) {
            valueSpan.textContent = data?.count || 0;
        }
    }

    if (directionPositive) {
        directionPositive.textContent = `▲ ${data?.count_by_direction?.positive ?? data?.positive ?? 0}`;
    }

    if (directionNegative) {
        directionNegative.textContent = `▼ ${data?.count_by_direction?.negative ?? data?.negative ?? 0}`;
    }

    if (statusEl) {
        if (state === "no-data") {
            statusEl.textContent = "no data";
        } else if (state === "loading") {
            statusEl.textContent = "loading";
        } else {
            const timestamp = data?.timestamp;
            statusEl.textContent = timestamp
                ? `last update: ${new Date(timestamp).toLocaleTimeString()}`
                : "online";
        }
    }
}

initializeMap();

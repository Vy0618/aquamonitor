import { fetchStations } from "./api.js";
import { HEATMAP_CONFIG } from "./config.js";
import {
    filterStations,
    initializeFilterEvents,
    initializeFilters
} from "./filters.js";
import {
    createHeatmap,
    initializeMapEvents,
    updateMap
} from "./heatmap.js";
import { createMap } from "./map.js";
import { createMarkerLayer, updateMarkers } from "./markers.js";
import { startUptime } from "./uptime.js";
import { createZoomIndicator, updateZoomIndicator } from "./zoom.js";
import { fetchBottleCount } from "./bottle-counter.js";

let currentStationId = null;
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

        const updateVisualization = () => {
            updateMap({
                map,
                heat,
                markerLayer,
                stations,
                filterStations,
                config: HEATMAP_CONFIG
            });
        };

        initializeFilterEvents(stations, updateVisualization);
        updateMarkers(map, markerLayer, stations);

        initializeMapEvents(map, () => {
            updateVisualization();
            updateZoomIndicator(map, zoomDisplay);
        });

        updateVisualization();

        // Start bottle count polling for the first station in the list
        if (stations.length > 0) {
            currentStationId = stations[0].station_id;
            startBottlePolling(currentStationId);
        }

        console.log("AquaDetector initialized successfully.");
    } catch (error) {
        console.error("Error initializing map:", error);
    }
}

function startBottlePolling(stationId) {
    if (bottlePollingInterval) {
        clearInterval(bottlePollingInterval);
    }

    currentStationId = stationId;
    const statusEl = document.getElementById("bottleStatus");
    if (statusEl) {
        statusEl.textContent = `polling station ${stationId}...`;
    }

    // Poll every 3 seconds as per the plan
    bottlePollingInterval = setInterval(async () => {
        try {
            const data = await fetchBottleCount(stationId);
            updateBottleCountDisplay(data);
        } catch (error) {
            console.error("Failed to fetch bottle count:", error);
            if (statusEl) {
                statusEl.textContent = "polling error";
            }
        }
    }, 3000);
}

function updateBottleCountDisplay(data) {
    const countEl = document.getElementById("bottleCount");
    const directionPositive = document.getElementById("directionPositive");
    const directionNegative = document.getElementById("directionNegative");
    const statusEl = document.getElementById("bottleStatus");

    if (countEl) {
        const valueSpan = countEl.querySelector(".count-value");
        if (valueSpan) {
            valueSpan.textContent = data.count;
        }
    }

    if (directionPositive) {
        directionPositive.textContent = `▲ ${data.count_by_direction?.positive || 0}`;
    }

    if (directionNegative) {
        directionNegative.textContent = `▼ ${data.count_by_direction?.negative || 0}`;
    }

    if (statusEl) {
        statusEl.textContent = `last update: ${new Date().toLocaleTimeString()}`;
    }
}

initializeMap();

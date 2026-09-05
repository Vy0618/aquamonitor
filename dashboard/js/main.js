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

async function initializeMap() {
    const map = createMap();
    const markerLayer = createMarkerLayer();
    const zoomDisplay = createZoomIndicator(map);

    startUptime();

    try {
        console.log("Loading stations...");

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

        console.log("AquaDetector initialized successfully.");
    } catch (error) {
        console.error("Error initializing map:", error);
    }
}

initializeMap();

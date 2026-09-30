import { HEATMAP_CONFIG } from "./config.js";
import { updateMarkers } from "./markers.js";

export function getStationDetectionCount(station) {
    const count = Number(station.detection_summary?.total ?? station.detections ?? 0);
    return Number.isFinite(count) && count > 0 ? count : 0;
}

export function calculateIntensity(detections, config = HEATMAP_CONFIG) {
    return Number.isFinite(detections) && detections > 0
        ? detections / config.referenceDetections : 0;
}

export function buildHeatData(stationList, config = HEATMAP_CONFIG) {
    return stationList.filter(station => getStationDetectionCount(station) > 0)
        .map(station => {
            const [longitude, latitude] = station.location.coordinates;
            return [Number(latitude), Number(longitude),
                calculateIntensity(getStationDetectionCount(station), config)];
        });
}

export function createHeatmap(
    map,
    stationList,
    config = HEATMAP_CONFIG
) {
    const heatData = buildHeatData(stationList, config);

    return L.heatLayer(
        heatData,
        {
            radius: config.radius,
            blur: config.blur,
            maxZoom: config.maxZoom,
            minOpacity: config.minOpacity,
            max: 1,
            gradient: config.gradient
        }
    ).addTo(map);
}

export function updateHeatmap(
    map,
    heat,
    stationList,
    config = HEATMAP_CONFIG
) {
    if (!heat) {
        return;
    }

    const heatData = buildHeatData(stationList, config);

    heat.setLatLngs(heatData);
    heat.setOptions({
        radius: config.radius
    });
}

export function updateMap({
    map,
    heat,
    markerLayer,
    stations,
    filterStations,
    onStationSelect,
    selectedStationId,
    config = HEATMAP_CONFIG,
    mode = "heat"
}) {
    const filteredStations = filterStations(stations);

    if (mode === "stations") {
        if (map.hasLayer(heat)) map.removeLayer(heat);
    } else {
        updateHeatmap(map, heat, filteredStations, config);
        if (!map.hasLayer(heat)) heat.addTo(map);
    }
    updateMarkers(map, markerLayer, filteredStations, onStationSelect, selectedStationId, mode);
}

export function initializeMapEvents(map, updateHeatmapOnly, updateZoomIndicator) {
    map.on("zoomend", () => {
        updateHeatmapOnly();
        updateZoomIndicator(map);
    });
}

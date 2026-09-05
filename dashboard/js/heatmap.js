import { HEATMAP_CONFIG } from "./config.js";
import { updateMarkers } from "./markers.js";

export function calculateIntensity(
    detections,
    maxDetections,
    zoom,
    config = HEATMAP_CONFIG
) {
    if (zoom >= config.highZoom.minZoom) {
        return Math.min(
            detections / config.highZoom.maxDetections,
            1
        );
    }

    if (maxDetections <= 0) {
        return 0;
    }

    return Math.log1p(detections) / Math.log1p(maxDetections);
}

export function calculateHeatRadius(zoom, config = HEATMAP_CONFIG) {
    if (zoom <= 12) {
        return config.radius.state;
    }

    if (zoom < 15) {
        return config.radius.regional;
    }

    if (zoom <= config.municipal.maxZoom) {
        return config.radius.neighborhood;
    }

    return config.radius.close;
}

export function buildHeatData(
    stationList,
    zoom,
    config = HEATMAP_CONFIG
) {
    const maxDetections = Math.max(
        0,
        ...stationList.map(station => Number(station.detections))
    );

    const heatData = stationList.map(station => {
        const longitude = Number(station.location.coordinates[0]);
        const latitude = Number(station.location.coordinates[1]);
        const detections = Number(station.detections);

        return [
            latitude,
            longitude,
            calculateIntensity(detections, maxDetections, zoom, config)
        ];
    });

    return { heatData, maxDetections };
}

export function createHeatmap(
    map,
    stationList,
    config = HEATMAP_CONFIG
) {
    const zoom = map.getZoom();
    const { heatData } = buildHeatData(stationList, zoom, config);

    return L.heatLayer(
        heatData,
        {
            radius: calculateHeatRadius(zoom, config),
            blur: config.blur,
            maxZoom: config.maxZoom,
            minOpacity: config.minOpacity
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

    const zoom = map.getZoom();
    const { heatData } = buildHeatData(stationList, zoom, config);

    heat.setLatLngs(heatData);
    heat.setOptions({
        radius: calculateHeatRadius(zoom, config)
    });
}

export function updateMap({
    map,
    heat,
    markerLayer,
    stations,
    filterStations,
    config = HEATMAP_CONFIG
}) {
    const filteredStations = filterStations(stations);

    console.log("Estações exibidas:", filteredStations.length);

    updateHeatmap(map, heat, filteredStations, config);
    updateMarkers(map, markerLayer, filteredStations);
}

export function initializeMapEvents(map, updateVisualization) {
    map.on("zoomend", updateVisualization);
}

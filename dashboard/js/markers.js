import { HEATMAP_CONFIG } from "./config.js";

export function createMarkerLayer() {
    return L.layerGroup();
}

export function createMarker(station) {
    const longitude = Number(station.location.coordinates[0]);
    const latitude = Number(station.location.coordinates[1]);
    const detections = Number(station.detections);
    const marker = L.marker([latitude, longitude]);

    marker.bindPopup(`
        <b>
            Station ${station.station_id}
        </b>

        <br>

        Detections:
        ${detections}
    `);

    return marker;
}

export function updateMarkers(map, markerLayer, stationList) {
    markerLayer.clearLayers();

    stationList.forEach(station => {
        markerLayer.addLayer(createMarker(station));
    });

    updateMarkerVisibility(map, markerLayer);
}

export function updateMarkerVisibility(
    map,
    markerLayer,
    config = HEATMAP_CONFIG
) {
    if (map.getZoom() >= config.markers.minZoom) {
        if (!map.hasLayer(markerLayer)) {
            markerLayer.addTo(map);
        }

        return;
    }

    if (map.hasLayer(markerLayer)) {
        map.removeLayer(markerLayer);
    }
}

import { HEATMAP_CONFIG } from "./config.js";

export function createMarkerLayer() {
    return L.layerGroup();
}

function getBottleCount(station) {
    return station.bottle_count || {};
}

function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "no data";
    }

    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? "no data" : date.toLocaleString();
}

export function createMarker(station, onStationSelect) {
    const longitude = Number(station.location.coordinates[0]);
    const latitude = Number(station.location.coordinates[1]);
    const bottleCount = getBottleCount(station);
    const count = Number(bottleCount.count || 0);
    const positive = Number(bottleCount.positive || 0);
    const negative = Number(bottleCount.negative || 0);
    const marker = L.marker([latitude, longitude]);

    marker.bindPopup(`
        <b>
            Station ${station.station_id}
        </b>

        <br>

        <br>
        Bottle count: ${count}
        <br>
        Positive: ${positive}
        <br>
        Negative: ${negative}
        <br>
        Last update: ${formatTimestamp(bottleCount.timestamp)}
    `);

    if (onStationSelect) {
        marker.on("click", () => onStationSelect(station.station_id));
    }

    return marker;
}

export function updateMarkers(map, markerLayer, stationList, onStationSelect, selectedStationId) {
    markerLayer.clearLayers();

    stationList.forEach(station => {
        const marker = createMarker(station, onStationSelect);
        markerLayer.addLayer(marker);
    });

    updateMarkerVisibility(map, markerLayer);

    // Reopen the popup for the previously selected station so it
    // survives the layer refresh caused by polling / zoom updates.
    if (selectedStationId != null) {
        const station = stationList.find(s => s.station_id === selectedStationId);
        if (station) {
            const lat = Number(station.location.coordinates[1]);
            const lng = Number(station.location.coordinates[0]);
            const match = markerLayer.getLayers().find(m => {
                const ll = m.getLatLng();
                return Math.abs(ll.lat - lat) < 0.0001 && Math.abs(ll.lng - lng) < 0.0001;
            });
            if (match) {
                match.openPopup();
            }
        }
    }
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

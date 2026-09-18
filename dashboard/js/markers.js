import { HEATMAP_CONFIG } from "./config.js";

export function createMarkerLayer() {
    return L.layerGroup();
}

function getDetectionSummary(station) {
    return station.detection_summary || {};
}

function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "no data";
    }

    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? "no data" : date.toLocaleString();
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

export function createMarker(station, onStationSelect) {
    const longitude = Number(station.location.coordinates[0]);
    const latitude = Number(station.location.coordinates[1]);
    const summary = getDetectionSummary(station);
    const count = Number(summary.total || 0);
    const types = Object.entries(summary.by_type || {})
        .map(([type, total]) => `${escapeHtml(type)}: ${Number(total) || 0}`)
        .join(", ") || "no detections";
    const marker = L.marker([latitude, longitude], {
        autoPan: false,
        icon: L.divIcon({
            className: "station-marker",
            html: `<div class="station-marker__pin" title="Station ${station.station_id}">
                <strong>S${station.station_id}</strong><span>${count}</span>
            </div>`,
            iconSize: [42, 42],
            iconAnchor: [21, 21],
            popupAnchor: [0, -22],
        }),
    });

    marker.bindPopup(`
        <b>
            Station ${escapeHtml(station.station_id)}
        </b>

        <br>

        <br>
        Total detections: ${count}
        <br>
        Types: ${types}
        <br>
        Last detection: ${formatTimestamp(summary.timestamp)}
    `, { autoPan: false});

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

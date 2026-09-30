import { detectionTypeLabel } from "./labels.js";
import { formatBottleDirections } from "./directions.js";
import { HEATMAP_CONFIG } from "./config.js";

export function createMarkerLayer() {
    return L.layerGroup();
}

function getDetectionSummary(station) {
    return station.detection_summary || {};
}

function formatTimestamp(timestamp) {
    if (!timestamp) {
        return "Sem dados";
    }

    const date = new Date(timestamp);
    return Number.isNaN(date.getTime()) ? "Sem dados" : date.toLocaleString("pt-BR");
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

export function markerDiameter(count, mode = "stations") {
    if (mode === "both") return 12;
    return Math.max(8, 48 * Math.sqrt(Math.min(Math.max(count, 0) / HEATMAP_CONFIG.referenceDetections, 1)));
}

export function createMarker(station, onStationSelect, mode = "stations", selected = false) {
    const longitude = Number(station.location.coordinates[0]);
    const latitude = Number(station.location.coordinates[1]);
    const summary = getDetectionSummary(station);
    const rawCount = Number(summary.total ?? station.detections ?? 0);
    const count = Number.isFinite(rawCount) && rawCount > 0 ? rawCount : 0;
    const diameter = markerDiameter(count, mode);
    const label = `Estação ${station.station_id}: ${count.toLocaleString("pt-BR")} detecções`;
    const types = Object.entries(summary.by_type || {})
        .map(([type, total]) => `${escapeHtml(detectionTypeLabel(type))}: ${(Number(total) || 0).toLocaleString("pt-BR")}`)
        .join(", ") || "Nenhuma detecção";
    const marker = L.marker([latitude, longitude], {
        autoPan: false,
        title: label,
        alt: label,
        icon: L.divIcon({
            className: `station-marker station-marker--${mode}${selected ? " station-marker--selected" : ""}`,
            html: `<div class="station-dot" style="width:${diameter}px;height:${diameter}px"></div>`,
            iconSize: [Math.max(24, diameter), Math.max(24, diameter)],
            iconAnchor: [Math.max(24, diameter) / 2, Math.max(24, diameter) / 2],
            popupAnchor: [0, -diameter / 2],
        }),
    });

    marker.bindTooltip(escapeHtml(label));
    marker.stationId = station.station_id;

    marker.bindPopup(`
        <b>
            Estação ${escapeHtml(station.station_id)}
        </b>

        <br>

        <br>
        Total de detecções: ${count.toLocaleString("pt-BR")}
        <br>
        Tipos: ${types}
        <br>
        Sentido das garrafas: ${formatBottleDirections(summary)}
        <br>
        Última detecção: ${formatTimestamp(summary.timestamp)}
    `, { autoPan: false});

    if (onStationSelect) {
        marker.on("click", () => onStationSelect(station.station_id));
    }

    return marker;
}

export function updateMarkers(map, markerLayer, stationList, onStationSelect, selectedStationId, mode = "heat") {
    const popupWasOpen = markerLayer.getLayers().some(marker => marker.isPopupOpen());
    const previousSelected = markerLayer.getLayers().find(marker => marker.stationId === selectedStationId);
    const selectionChanged = !previousSelected || !previousSelected.options.icon.options.className.includes("station-marker--selected");
    markerLayer.clearLayers();
    if (mode === "heat") {
        if (map.hasLayer(markerLayer)) map.removeLayer(markerLayer);
        return;
    }

    if (!map.hasLayer(markerLayer)) markerLayer.addTo(map);
    stationList.forEach(station => {
        const selected = station.station_id === selectedStationId;
        const marker = createMarker(station, onStationSelect, mode, selected);
        markerLayer.addLayer(marker);
        if (selected && (popupWasOpen || selectionChanged)) marker.openPopup();
    });
}

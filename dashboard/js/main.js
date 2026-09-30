import { detectionTypeLabel } from "./labels.js";
import { formatBottleDirections } from "./directions.js";
import { fetchStations } from "./api.js";
import { HEATMAP_CONFIG } from "./config.js";
import { clearFilters, filterStations, initializeFilterEvents, initializeFilters, refreshFilters } from "./filters.js";
import { createHeatmap, initializeMapEvents, updateMap } from "./heatmap.js";
import { createMap, fitMapToStations } from "./map.js";
import { createMarkerLayer } from "./markers.js";
import { startUptime } from "./uptime.js";
import { createZoomIndicator, updateZoomIndicator } from "./zoom.js";
import { initializeStationSearch } from "./station-search.js";
import { updateCityRanking } from "./city-ranking.js";

let selectedStationId = null;

async function initializeMap() {
    const map = createMap();
    const markerLayer = createMarkerLayer();
    const zoomDisplay = createZoomIndicator(map);
    const modeSelect = document.getElementById("mapMode");
    const reference = HEATMAP_CONFIG.referenceDetections.toLocaleString("pt-BR");
    document.getElementById("heatLegendReference").textContent =
        `Escala fixa: referência de saturação em ${reference} detecções. A cor também depende da sobreposição das manchas.`;
    document.getElementById("heatLegendGradient").style.background = `linear-gradient(to right, ${
        Object.entries(HEATMAP_CONFIG.gradient).sort(([a], [b]) => Number(a) - Number(b))
            .map(([stop, color]) => `${color} ${Number(stop) * 100}%`).join(", ")})`;
    function updateLegend() {
        document.getElementById("heatLegend").hidden = modeSelect.value === "stations";
        const stationLegend = document.getElementById("stationLegend");
        stationLegend.hidden = modeSelect.value === "heat";
        stationLegend.textContent = modeSelect.value === "both"
            ? "Anéis pequenos indicam as estações. Selecione um deles para consultar as detecções."
            : `Área dos círculos proporcional às detecções, até ${reference}. Valores maiores atingem o tamanho máximo; valores baixos e zero usam o tamanho mínimo para seleção. Selecione para ver o total exato.`;
    }
    updateLegend();
    startUptime();

    {
        const stations = [];
        initializeFilters(stations);
        updateCityRanking(stations);
        const heat = createHeatmap(map, stations, HEATMAP_CONFIG);

        const updateVisualization = () => updateMap({
            map, heat, markerLayer, stations, filterStations,
            onStationSelect: selectStation, selectedStationId, config: HEATMAP_CONFIG,
            mode: modeSelect.value
        });
        modeSelect.addEventListener("change", () => {
            updateLegend();
            updateVisualization();
        });

        function selectStation(stationId) {
            selectedStationId = stationId;
            document.getElementById("selectedStation").textContent = `Estação #${stationId}`;
            const station = stations.find(item => item.station_id === stationId);
            if (station) {
                updateDetectionDisplay(station.detection_summary, station.detection_summary?.timestamp ? "online" : "no-data");
            }

        }

        initializeFilterEvents(stations, updateVisualization, filteredStations => {
            fitMapToStations(map, filteredStations);
        });
        initializeStationSearch(stations, station => {
            if (modeSelect.value === "heat") {
                modeSelect.value = "both";
                updateLegend();
            }
            if (!filterStations(stations).includes(station)) {
                clearFilters(stations, updateVisualization);
            }
            selectStation(station.station_id);
            const [longitude, latitude] = station.location.coordinates;
            map.setView([Number(latitude), Number(longitude)],
                Math.max(map.getZoom(), 16));
            updateVisualization();
        });
        initializeMapEvents(map, updateVisualization, () => updateZoomIndicator(map, zoomDisplay));
        updateVisualization();
        let hasLoaded = false;
        let lastUpdated = null;
        const status = document.getElementById("systemStatus");
        async function refreshDashboard() {
            try {
                const latestStations = await fetchStations();
                // Conserva a referência usada pelos eventos dos filtros e da busca.
                stations.splice(0, stations.length, ...latestStations);
                refreshFilters(stations);
                updateCityRanking(stations);
                const selected = stations.find(station => station.station_id === selectedStationId);
                if (selected) {
                    selectStation(selected.station_id);
                } else if (!hasLoaded && stations.length > 0) {
                    selectStation(stations[0].station_id);
                } else {
                    selectedStationId = null;
                    document.getElementById("selectedStation").textContent = "Nenhuma estação selecionada";
                    updateDetectionDisplay(null, "no-data");
                }
                updateVisualization();
                hasLoaded = true;
                lastUpdated = new Date().toLocaleTimeString("pt-BR");
                status.textContent = `Atualizado às ${lastUpdated}`;
                status.classList.remove("system-status--error");
            } catch (error) {
                console.error("Erro ao atualizar o painel:", error);
                status.textContent = lastUpdated
                    ? `Falha na atualização · dados de ${lastUpdated} · nova tentativa em 5 s`
                    : "Sem conexão · nova tentativa em 5 s";
                status.classList.add("system-status--error");
                if (!hasLoaded) {
                    document.getElementById("cityRankingStatus").textContent = "Aguardando conexão com o servidor.";
                }
            } finally {
                // Agenda após a conclusão para não acumular requisições lentas.
                setTimeout(refreshDashboard, 5000);
            }
        }
        await refreshDashboard();
    }
}

function updateDetectionDisplay(data, state = "loading") {
    document.getElementById("bottleDirections").textContent = formatBottleDirections(data);
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

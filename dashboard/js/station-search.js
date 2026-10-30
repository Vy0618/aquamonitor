export function initializeStationSearch(stations, onStationFound) {
    const form = document.getElementById("stationSearchForm");
    const input = document.getElementById("stationSearch");
    const status = document.getElementById("stationSearchStatus");

    input.disabled = false;
    document.getElementById("stationSearchButton").disabled = false;
    status.textContent = "";

    form.addEventListener("submit", event => {
        event.preventDefault();
        const id = input.value.trim();
        if (!id) {
            status.textContent = "Digite o ID da estação.";
            input.focus();
            return;
        }

        const station = stations.find(item => String(item.station_id) === id);
        if (!station) {
            status.textContent = `Nenhuma estação encontrada com o ID ${id}.`;
            return;
        }

        onStationFound(station);
        status.textContent = `Estação ${station.station_id} localizada no mapa.`;
    });

    input.addEventListener("input", () => { status.textContent = ""; });
    document.getElementById("clearFilters").addEventListener("click", () => {
        input.value = "";
        status.textContent = "";
    });
}

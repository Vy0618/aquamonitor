export function fitMapToStations(map, stations) {
    const coordinates = stations.map(station => {
        const [longitude, latitude] = station.location.coordinates;
        return [Number(latitude), Number(longitude)];
    });

    if (coordinates.length === 0) return;

    map.fitBounds(coordinates, { padding: [40, 40], maxZoom: 16 });
}

export function createMap() {
    const map = L.map("map", { zoomControl: false }).setView(
        [-23.5015, -46.4526],
        13
    );

    L.control.zoom({ zoomInTitle: "Ampliar", zoomOutTitle: "Reduzir" }).addTo(map);
    map.on("popupopen", ({ popup }) => {
        const closeButton = popup.getElement()?.querySelector(".leaflet-popup-close-button");
        if (closeButton) {
            closeButton.setAttribute("aria-label", "Fechar detalhes da estação");
            closeButton.title = "Fechar detalhes da estação";
        }
    });

    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">Colaboradores do OpenStreetMap</a>'
        }
    ).addTo(map);

    return map;
}

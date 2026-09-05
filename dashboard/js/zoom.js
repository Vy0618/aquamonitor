export function createZoomIndicator(map) {
    const zoomDisplay = L.control({
        position: "topright"
    });

    zoomDisplay.onAdd = function () {
        const div = L.DomUtil.create(
            "div",
            "zoom-indicator"
        );

        div.innerHTML = `Zoom: ${map.getZoom()}`;

        return div;
    };

    zoomDisplay.addTo(map);

    return zoomDisplay;
}

export function updateZoomIndicator(map, zoomDisplay) {
    const container = zoomDisplay.getContainer();

    if (container) {
        container.innerHTML = `Zoom: ${map.getZoom()}`;
    }
}

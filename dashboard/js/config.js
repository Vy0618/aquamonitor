export const HEATMAP_CONFIG = {
    // Referência fixa: não muda com filtros ou ampliação.
    referenceDetections: 300,
    minOpacity: 0.01,
    radius: 24,
    blur: 16,
    // Desativa a redução automática de intensidade em ampliações menores.
    maxZoom: 0,
    gradient: {
        0.0: "#243b80",
        0.25: "#287fc1",
        0.5: "#43c6a2",
        0.75: "#f4d35e",
        1.0: "#ef553b"
    }
};

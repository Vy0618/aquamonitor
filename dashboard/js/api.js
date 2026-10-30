const api_url = "http://127.0.0.1:8000/api/stations";

export async function fetchStations() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
        const response = await fetch(api_url, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error(`Erro na API: ${response.status}`);
        const stations = await response.json();
        if (!Array.isArray(stations)) throw new Error("Lista de estações inválida.");
        return stations;
    } finally {
        clearTimeout(timeout);
    }
}

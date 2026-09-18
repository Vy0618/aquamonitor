const API_URL = "http://127.0.0.1:8000/api/stations";

export async function fetchDetectionSummary(stationId) {
    const response = await fetch(`${API_URL}/${stationId}/detections`);
    if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
    }
    return response.json();
}

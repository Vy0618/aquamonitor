const api_url = "http://127.0.0.1:8000/api/stations";

export async function fetchStations() {

    const response = await fetch(
        api_url
    );

    if (!response.ok) {

        throw new Error(
            `API error: ${response.status}`
        );

    }

    return response.json();

}
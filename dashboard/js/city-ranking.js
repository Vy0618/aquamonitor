export function rankCities(stations) {
    const cities = new Map();

    for (const station of stations) {
        const city = station.administrative?.city?.trim();
        if (!city) continue;
        const state = station.administrative?.state?.trim() || "Estado não informado";
        const key = JSON.stringify([state, city]);
        const entry = cities.get(key) || { city, state, total: 0 };
        const count = Number(station.detection_summary?.total ?? station.detections ?? 0);
        entry.total += Number.isFinite(count) && count > 0 ? count : 0;
        cities.set(key, entry);
    }

    return [...cities.values()].sort((a, b) =>
        b.total - a.total
        || a.city.localeCompare(b.city, "pt-BR")
        || a.state.localeCompare(b.state, "pt-BR")
    );
}

export function updateCityRanking(stations) {
    const list = document.getElementById("cityRanking");
    const ranking = rankCities(stations).slice(0, 5);
    list.replaceChildren();

    for (const entry of ranking) {
        const item = document.createElement("li");
        const location = document.createElement("span");
        location.className = "ranking-location";
        location.textContent = entry.city;
        const state = document.createElement("small");
        state.textContent = entry.state;
        location.appendChild(state);
        const count = document.createElement("span");
        count.className = "ranking-count";
        count.textContent = entry.total.toLocaleString("pt-BR");
        count.setAttribute("aria-label", `${entry.total} detecções`);
        item.append(location, count);
        list.appendChild(item);
    }

    document.getElementById("cityRankingStatus").textContent = ranking.length
        ? "" : "Nenhum município cadastrado.";
}

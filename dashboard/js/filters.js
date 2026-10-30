export function getUniqueValues(stationList, property) {
    return [
        ...new Set(
            stationList
                .map(station => station.administrative?.[property])
                .filter(Boolean)
        )
    ].sort();
}

export function populateSelect(selectId, values, defaultText) {
    const select = document.getElementById(selectId);

    if (!select) {
        return;
    }

    select.innerHTML = "";

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = defaultText;
    select.appendChild(defaultOption);

    values.forEach(value => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });
}

export function getFilterValues() {
    return {
        state: document.getElementById("stateFilter")?.value || "",
        city: document.getElementById("cityFilter")?.value || "",
        district: document.getElementById("districtFilter")?.value || ""
    };
}

export function matchesAdministrativeFilter(station, filters) {
    const administrative = station.administrative;

    if (filters.state && administrative?.state !== filters.state) {
        return false;
    }

    if (filters.city && administrative?.city !== filters.city) {
        return false;
    }

    if (filters.district && administrative?.district !== filters.district) {
        return false;
    }

    return true;
}

export function filterStations(stationList) {
    const filters = getFilterValues();

    return stationList.filter(station =>
        matchesAdministrativeFilter(station, filters)
    );
}

export function initializeFilters(stationList) {
    const states = getUniqueValues(stationList, "state");

    populateSelect("stateFilter", states, "Todos os estados");
    updateCityFilter(stationList);
}

export function refreshFilters(stationList) {
    const selected = getFilterValues();
    const refreshSelect = (id, values, label, previous) => {
        const select = document.getElementById(id);
        if (!select) return;
        const current = Array.from(select.options).slice(1).map(option => option.value);
        if (JSON.stringify(current) !== JSON.stringify(values)) {
            populateSelect(id, values, label);
        }
        select.value = values.includes(previous) ? previous : "";
        return select.value;
    };
    const state = refreshSelect("stateFilter", getUniqueValues(stationList, "state"),
        "Todos os estados", selected.state);
    const stateStations = stationList.filter(station => !state || station.administrative?.state === state);
    const city = refreshSelect("cityFilter", getUniqueValues(stateStations, "city"),
        "Todos os municípios", selected.city);
    const cityStations = stateStations.filter(station => !city || station.administrative?.city === city);
    refreshSelect("districtFilter", getUniqueValues(cityStations, "district"),
        "Todos os distritos", selected.district);
}

export function updateCityFilter(stationList) {
    const state = document.getElementById("stateFilter")?.value || "";
    const filtered = stationList.filter(station =>
        !state || station.administrative?.state === state
    );
    const cities = getUniqueValues(filtered, "city");

    populateSelect("cityFilter", cities, "Todos os municípios");
    updateDistrictFilter(stationList);
}

export function updateDistrictFilter(stationList) {
    const state = document.getElementById("stateFilter")?.value || "";
    const city = document.getElementById("cityFilter")?.value || "";
    const filtered = stationList.filter(station => {
        const administrative = station.administrative;

        return (
            (!state || administrative?.state === state)
            && (!city || administrative?.city === city)
        );
    });
    const districts = getUniqueValues(filtered, "district");

    populateSelect("districtFilter", districts, "Todos os distritos");
}

export function applyFilters(updateVisualization) {
    updateVisualization();
}

export function clearFilters(stationList, updateVisualization) {
    const stateFilter = document.getElementById("stateFilter");
    const cityFilter = document.getElementById("cityFilter");
    const districtFilter = document.getElementById("districtFilter");

    if (stateFilter) {
        stateFilter.value = "";
    }

    updateCityFilter(stationList);

    if (cityFilter) {
        cityFilter.value = "";
    }

    updateDistrictFilter(stationList);

    if (districtFilter) {
        districtFilter.value = "";
    }

    updateVisualization();
}

export function initializeFilterEvents(stationList, updateVisualization, onLocationChange = () => {}) {
    const updateLocation = () => {
        updateVisualization();
        onLocationChange(filterStations(stationList));
    };
    const stateFilter = document.getElementById("stateFilter");
    const cityFilter = document.getElementById("cityFilter");
    const districtFilter = document.getElementById("districtFilter");
    const applyButton = document.getElementById("applyFilters");
    const clearButton = document.getElementById("clearFilters");

    if (stateFilter) {
        stateFilter.addEventListener("change", () => {
            updateCityFilter(stationList);
            updateLocation();
        });
    }

    if (cityFilter) {
        cityFilter.addEventListener("change", () => {
            updateDistrictFilter(stationList);
            updateLocation();
        });
    }

    if (districtFilter) {
        districtFilter.addEventListener("change", updateLocation);
    }

    if (applyButton) {
        applyButton.addEventListener(
            "click",
            () => applyFilters(updateLocation)
        );
    }

    if (clearButton) {
        clearButton.addEventListener(
            "click",
            () => clearFilters(stationList, updateLocation)
        );
    }
}

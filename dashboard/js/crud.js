const form = document.getElementById("stationForm");
const message = document.getElementById("message");


form.addEventListener("submit", async (event) => {

    event.preventDefault();


    const station_id =
        Number(document.getElementById("station_id").value);

    const detections =
        Number(document.getElementById("detections").value);

    const longitude =
        Number(document.getElementById("longitude").value);

    const latitude =
        Number(document.getElementById("latitude").value);


    const station = {

        station_id: station_id,

        detections: detections,

        location: {
            type: "Point",
            coordinates: [
                longitude,
                latitude
            ]
        }

    };


    try {

        const response = await fetch(
            "http://127.0.0.1:8000/api/stations",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify(station)
            }
        );


        const data = await response.json();


        if (!response.ok) {
            throw new Error(
                data.detail || "Failed to add station"
            );
        }


        message.textContent =
            "Station added successfully.";

        form.reset();


    } catch (error) {

        console.error(error);

        message.textContent =
            "Error: " + error.message;

    }

});

// ==========================================
// DELETE STATION
// ==========================================

const deleteForm =
    document.getElementById("deleteForm");

const deleteMessage =
    document.getElementById("deleteMessage");


deleteForm.addEventListener("submit", async (event) => {

    event.preventDefault();


    const station_id =
        document
            .getElementById("delete_station_id")
            .value
            .trim();


    if (!station_id) {

        deleteMessage.textContent =
            "Please enter a Station ID.";

        return;

    }


    // Confirmar exclusão

    const confirmed = confirm(
        `Are you sure you want to delete station ${station_id}?`
    );


    if (!confirmed) {
        return;
    }


    try {

        const response = await fetch(
            `http://127.0.0.1:8000/api/stations/${encodeURIComponent(station_id)}`,
            {
                method: "DELETE"
            }
        );


        const data = await response.json();


        if (!response.ok) {

            throw new Error(
                data.detail || "Failed to delete station"
            );

        }


        deleteMessage.textContent =
            "Station deleted successfully.";

        deleteForm.reset();


    } catch (error) {

        console.error(error);

        deleteMessage.textContent =
            "Error: " + error.message;

    }

});
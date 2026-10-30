const form = document.getElementById("stationForm");
const message = document.getElementById("message");


form.addEventListener("submit", async (event) => {

    event.preventDefault();


    const station_id =
        Number(document.getElementById("station_id").value);

    const country =
        document.getElementById("country").value.trim();

    const state =
        document.getElementById("state").value.trim();

    const city =
        document.getElementById("city").value.trim();

    const district =
        document.getElementById("district").value.trim();

    const longitude =
        Number(document.getElementById("longitude").value);

    const latitude =
        Number(document.getElementById("latitude").value);


    const station = {

        station_id: station_id,
        administrative: {
            country: country,
            state: state,
            city: city,
            district: district
        },
        location: {
            type: "Point",
            coordinates: [longitude, latitude]
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


        // As mensagens são traduzidas conforme o status da resposta.


        if (!response.ok) {
            throw new Error(
                response.status === 409 ? "Já existe uma estação com esse ID." : response.status === 422 ? "Dados inválidos. Confira os campos e informe um ID inteiro positivo." : "Não foi possível cadastrar a estação."
            );
        }


        message.textContent =
            "Estação cadastrada com sucesso.";

        form.reset();


    } catch (error) {

        console.error(error);

        message.textContent =
            "Erro: " + (error instanceof TypeError ? "Não foi possível conectar ao servidor." : error.message);

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
            "Informe o ID da estação.";

        return;

    }


    // Confirmar exclusão

    const confirmed = confirm(
        `Tem certeza de que deseja excluir a estação ${station_id}?`
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


        // As mensagens são traduzidas conforme o status da resposta.


        if (!response.ok) {

            throw new Error(
                response.status === 404 ? "Estação não encontrada." : response.status === 422 ? "ID da estação inválido." : "Não foi possível excluir a estação."
            );

        }


        deleteMessage.textContent =
            "Estação excluída com sucesso.";

        deleteForm.reset();


    } catch (error) {

        console.error(error);

        deleteMessage.textContent =
            "Erro: " + (error instanceof TypeError ? "Não foi possível conectar ao servidor." : error.message);

    }

});
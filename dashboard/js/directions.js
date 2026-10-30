export function bottleDirections(summary) {
    const directions = summary?.by_type_direction?.bottle;
    return directions || { positive: 0, negative: 0, unknown: Number(summary?.by_type?.bottle || 0) };
}

export function formatBottleDirections(summary) {
    const directions = bottleDirections(summary);
    return `↓ Positivo: ${Number(directions.positive || 0).toLocaleString("pt-BR")} · `
        + `↑ Negativo: ${Number(directions.negative || 0).toLocaleString("pt-BR")} · `
        + `Não informado: ${Number(directions.unknown || 0).toLocaleString("pt-BR")}`;
}

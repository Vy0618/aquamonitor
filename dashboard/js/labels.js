const detectionTypes = new Map([
    ["bottle", "Garrafa"],
    ["can", "Lata"],
    ["carton", "Papelão"],
    ["paper", "Papel"],
    ["plastic", "Plástico"]
]);

export function detectionTypeLabel(type) {
    return detectionTypes.get(type) || type;
}

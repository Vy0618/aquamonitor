export const systemStart = Date.now();

export function updateUptime() {
    const uptimeElement = document.getElementById("uptime");

    if (!uptimeElement) {
        return;
    }

    const elapsed = Date.now() - systemStart;
    const totalSeconds = Math.floor(elapsed / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const formatted =
        String(hours).padStart(2, "0")
        + ":"
        + String(minutes).padStart(2, "0")
        + ":"
        + String(seconds).padStart(2, "0");

    uptimeElement.textContent = formatted;
}

export function startUptime() {
    updateUptime();

    return setInterval(updateUptime, 1000);
}

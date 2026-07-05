// Auto-scroll terminal output to the bottom when new logs arrive
let lastTerminalLength = -1;

function scrollTerminalToBottom() {
    const textarea = document.querySelector('#terminal-output textarea');
    if (!textarea) return;

    const currentLength = textarea.value.length;
    if (currentLength !== lastTerminalLength) {
        textarea.scrollTop = textarea.scrollHeight;
        lastTerminalLength = currentLength;
    }
}

// Poll terminal scroll (very lightweight, 100ms interval for near-instant response)
if (window.terminalScrollIntervalId) {
    clearInterval(window.terminalScrollIntervalId);
}
window.terminalScrollIntervalId = setInterval(scrollTerminalToBottom, 100);

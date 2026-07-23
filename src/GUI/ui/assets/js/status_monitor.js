// Dynamic status class toggling for status-box
function updateStatusClass() {
    const statusBox = document.getElementById('status-box');
    if (!statusBox) return;

    const inputEl = statusBox.querySelector('textarea') || statusBox.querySelector('input');
    if (!inputEl) return;

    const val = inputEl.value ? inputEl.value.trim().toLowerCase() : '';
    
    // Remove previous status classes
    statusBox.classList.remove('status-running', 'status-finished', 'status-failed', 'status-stopped', 'status-ready');
    
    if (val === 'running') {
        statusBox.classList.add('status-running');
    } else if (val === 'finished' || val === 'success') {
        statusBox.classList.add('status-finished');
    } else if (val === 'failed' || val === 'error') {
        statusBox.classList.add('status-failed');
    } else if (val === 'stopped') {
        statusBox.classList.add('status-stopped');
    } else if (val === 'ready') {
        statusBox.classList.add('status-ready');
    }
}

// Start polling status box state
if (window.statusIntervalId) {
    clearInterval(window.statusIntervalId);
}
window.statusIntervalId = setInterval(updateStatusClass, 250);

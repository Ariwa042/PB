const socket = io();
let currentJobId = null;

function formatTime(date) {
    // Format time in 24-hour format with seconds
    return date.toISOString().split('T')[1].split('.')[0]; // HH:MM:SS
}

function addLogEntry(message, type = 'info') {
    const logsDiv = document.getElementById('logs');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    entry.innerHTML = `<span class="text-gray-400">[${formatTime(new Date())}]</span> ${message}`;
    logsDiv.appendChild(entry);
    logsDiv.scrollTop = logsDiv.scrollHeight;
}

document.getElementById('floodForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    
    // Convert datetime-local to proper format (YYYY-MM-DD HH:MM:SS)
    if (data.scheduled_time) {
        const dt = new Date(data.scheduled_time);
        data.scheduled_time = dt.toISOString().replace('T', ' ').split('.')[0];
    }
    
    const submitButton = e.target.querySelector('button[type="submit"]');
    submitButton.disabled = true;
    submitButton.innerHTML = `
        <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Processing...
    `;
    
    try {
        const response = await fetch('/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        const result = await response.json();
        currentJobId = result.job_id;
        addLogEntry('Job submitted successfully...', 'success');
    } catch (error) {
        addLogEntry(`Error submitting job: ${error}`, 'error');
        submitButton.disabled = false;
        submitButton.innerHTML = 'Schedule Flood';
    }
});

socket.on('job_update', (data) => {
    if (data.job_id === currentJobId) {
        if (Array.isArray(data.logs)) {
            data.logs.forEach(log => {
                addLogEntry(log, log.includes('❌') ? 'error' : 'info');
            });
        }
        
        if (data.status === 'completed') {
            addLogEntry('Job completed successfully! 🎉', 'success');
            document.querySelector('button[type="submit"]').innerHTML = 'Schedule Flood';
        } else if (data.status === 'failed') {
            addLogEntry('Job failed! ❌', 'error');
            document.querySelector('button[type="submit"]').disabled = false;
            document.querySelector('button[type="submit"]').innerHTML = 'Retry';
        }
    }
});

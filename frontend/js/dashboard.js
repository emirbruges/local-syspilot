document.addEventListener('DOMContentLoaded', () => {
    // --- CARGAR DATOS DEL DASHBOARD ---
    fetch('/api/dashboard-data', {
        method: 'GET',
        credentials: 'include' // 👈 Necesario para enviar la cookie al backend
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Invalid or expired token.');
        }
        return response.json();
    })
    .then(result => {
        if (result.success) {
            const data = result.data;
            document.getElementById('cpu-usage').textContent = data.cpu_usage;
            document.getElementById('ram-usage').textContent = data.ram_usage;
            document.getElementById('uptime').textContent = data.uptime;
            document.getElementById('welcome-message').textContent = `Welcome, ${data.user}`;
        } else {
            throw new Error(result.message || 'Error getting dashboard data.');
        }
    })
    .catch(error => {
        console.error('Network or authentication error:', error);
        window.location.href = '/'; // Redirigir al login si hay problema
    });


    // --- LÓGICA DE LOS BOTONES ---
    const logoutButton = document.getElementById('logout-button');
    logoutButton.addEventListener('click', async () => {
        // Petición al backend para eliminar la cookie
        await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });

        window.location.href = '/'; // Volver al login
    });

    document.querySelector('.action-button.shutdown').addEventListener('click', () => {
        if (confirm('This is a simulation. Call API for shutdown?')) {
            console.log("Calling /api/shutdown with the token...");
        }
    });
});

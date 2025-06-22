document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('syspilot_token');

    // --- VERIFICACIÓN INICIAL ---
    // Si no hay token, no hay nada que hacer aquí. Redirigir inmediatamente.
    if (!token) {
        window.location.href = 'index.html';
        return;
    }

    // --- CARGAR DATOS DEL DASHBOARD ---
    // Intentar cargar los datos del dashboard desde el backend usando el token
    fetch('http://127.0.0.1:5000/api/dashboard-data', {
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${token}` // Enviar el token para autenticación
        }
    })
    .then(response => {
        if (!response.ok) {
            // Si la respuesta no es OK (ej. 401 No Autorizado), el token es inválido o expiró
            throw new Error('Token inválido o expirado');
        }
        return response.json();
    })
    .then(result => {
        if (result.success) {
            // Si todo fue bien, poblar el dashboard con los datos
            const data = result.data;
            document.getElementById('cpu-usage').textContent = data.cpu_usage;
            document.getElementById('ram-usage').textContent = data.ram_usage;
            document.getElementById('uptime').textContent = data.uptime;
            document.getElementById('welcome-message').textContent = `Bienvenido, ${data.user}`;
        } else {
            // Aunque la respuesta fue OK, pudo haber un error lógico en el backend
            throw new Error(result.message || 'Error al obtener los datos del dashboard');
        }
    })
    .catch(error => {
        console.error('Error de autenticación o de red:', error);
        // Cualquier error en la carga de datos (token malo, red, etc.) debe limpiar y redirigir
        localStorage.removeItem('syspilot_token');
        window.location.href = 'index.html';
    });


    // --- LÓGICA DE LOS BOTONES ---
    const logoutButton = document.getElementById('logout-button');
    logoutButton.addEventListener('click', () => {
        localStorage.removeItem('syspilot_token'); // Borra el token
        window.location.href = 'index.html'; // Vuelve al login
    });
    
    // Aquí puedes añadir la lógica para los otros botones de acción
    document.querySelector('.action-button.shutdown').addEventListener('click', () => {
        // En el futuro, esto llamaría a un endpoint protegido: /api/shutdown
        if(confirm('Esto es una simulación. ¿Llamar a la API para apagar?')) {
            console.log("Llamando a /api/shutdown con el token...");
        }
    });
});

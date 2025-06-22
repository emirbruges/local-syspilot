document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const errorMessage = document.getElementById('error-message');

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const username = loginForm.username.value;
        const password = loginForm.password.value;
        errorMessage.textContent = '';

        try {
            const response = await fetch('http://127.0.0.1:5000/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            const data = await response.json();

            if (data.success && data.token) {
                // Si el login es exitoso y recibimos un token, lo guardamos
                localStorage.setItem('syspilot_token', data.token);
                // Y redirigimos al dashboard
                window.location.href = 'dashboard.html';
            } else {
                errorMessage.textContent = data.message || 'Login fallido. Inténtalo de nuevo.';
            }
        } catch (error) {
            console.error('Error de conexión con el servidor:', error);
            errorMessage.textContent = 'No se puede conectar al servidor. ¿Está en ejecución?';
        }
    });
});

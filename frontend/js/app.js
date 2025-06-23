document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const errorMessage = document.getElementById('error-message');

    loginForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        const username = loginForm.username.value;
        const password = loginForm.password.value;
        errorMessage.textContent = '';

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
                credentials: 'include'
            });

            const data = await response.json();

            if (data.success) {
                window.location.href = '/dashboard';
            } else {
                errorMessage.textContent = data.message || 'Login failed. Try again.';
            }
        } catch (error) {
            console.error('Server connection error:', error);
            errorMessage.textContent = "Can't connect to server. Is it running ?";
        }
    });
});

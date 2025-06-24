document.addEventListener('DOMContentLoaded', () => {
    let userPermissions = {}; // Global variable to store user permissions
    let allPermissions = { // Definition of all possible permissions
        "shutdown": "Shutdown",
        "restart": "Reboot",
        "lock": "Lock Session",
        "play_pause": "Play/Pause",
        "volume": "Volume Control",
        "system_metrics": "System Metrics",
        "modify_commands": "Modify Commands", // Assuming this will be a permission for other controls
        "manage_users": "Manage Users"
    };

    // --- Modal DOM Elements ---

    // Volume control elements
    const volumeSlider = document.getElementById('volume-slider');
    const volumePercentageSpan = document.getElementById('volume-percentage');
    let volumeChangeTimer; // <--- ADD THIS LINE

    const userManagementModal = document.getElementById('user-management-modal');
    const closeButton = userManagementModal.querySelector('.close-button');
    const manageUsersButton = document.getElementById('manage-users-button');
    const manageUsersCard = document.getElementById('manage-users-card');

    const modalTabButtons = document.querySelectorAll('.modal-tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    const usersTableBody = document.querySelector('#users-table tbody');
    const noUsersMessage = document.getElementById('no-users-message');

    const addUserForm = document.getElementById('add-user-form');
    const addPermissionsCheckboxes = document.getElementById('add-permissions-checkboxes');
    const addUserErrorMessage = document.getElementById('add-user-error-message');

    const editUserModal = document.getElementById('edit-user-modal');
    const closeButtonNested = editUserModal.querySelector('.close-button-nested');
    const editUserForm = document.getElementById('edit-user-form');
    const editUserIdInput = document.getElementById('edit-user-id');
    const editUsernameTitle = document.getElementById('edit-username-title');
    const editPermissionsCheckboxes = document.getElementById('edit-permissions-checkboxes');
    const editUserErrorMessage = document.getElementById('edit-user-error-message');

    // Custom Alert/Message Modal Elements
    const customAlertModal = document.getElementById('custom-alert-modal');
    const customAlertMessage = document.getElementById('custom-alert-message');
    const customAlertOkButton = document.getElementById('custom-alert-ok-button');
    const closeButtonAlert = customAlertModal.querySelector('.close-button-alert');

    // --- Custom Alert/Message Modal Functions ---
    function showAlert(message) {
        customAlertMessage.textContent = message;
        customAlertModal.style.display = 'flex'; // Use flex for centering
    }

    closeButtonAlert.addEventListener('click', () => {
        customAlertModal.style.display = 'none';
    });
    customAlertOkButton.addEventListener('click', () => {
        customAlertModal.style.display = 'none';
    });
    // Close when clicking outside the alert modal content
    customAlertModal.addEventListener('click', (event) => {
        if (event.target === customAlertModal) {
            customAlertModal.style.display = 'none';
        }
    });


    // --- Function to update UI based on permissions ---
    function updateUIBasedOnPermissions() {
        // Disable power control buttons if no permissions
        document.querySelector('.action-button.shutdown').disabled = !userPermissions.shutdown;
        document.querySelector('.action-button.restart').disabled = !userPermissions.restart;
        document.querySelector('.action-button.lock').disabled = !userPermissions.lock;

        const playPauseButton = document.querySelector('.action-button.play-pause');
        
        if (playPauseButton) {
            playPauseButton.disabled = !userPermissions.play_pause;
        }
        
        // Volume slider and percentage span
        if (volumeSlider) { // Usa la constante volumeSlider
            volumeSlider.disabled = !userPermissions.volume;
            // Also update the percentage display based on initial value or if disabled
            volumePercentageSpan.textContent = userPermissions.volume ? `${volumeSlider.value}%` : 'N/A';
        }

        const metricsCard = document.querySelector('.control-card:nth-child(3)');
        if (metricsCard) {
            if (!userPermissions.system_metrics) {
                metricsCard.style.opacity = '0.5';
                metricsCard.style.pointerEvents = 'none';
                document.getElementById('cpu-usage').textContent = 'N/A';
                document.getElementById('ram-usage').textContent = 'N/A';
                document.getElementById('uptime').textContent = 'N/A';
            } else {
                metricsCard.style.opacity = '1';
                metricsCard.style.pointerEvents = 'auto';
            }
        }

        // Show/hide user management button
        if (userPermissions.manage_users) {
            manageUsersCard.style.display = 'block';
        } else {
            manageUsersCard.style.display = 'none';
        }
    }

    // --- User Management Modal Functions ---

    // Open modal
    manageUsersButton.addEventListener('click', () => {
        userManagementModal.style.display = 'flex'; // Use flex for centering
        loadUsers(); // Load user list when opening the modal
        renderPermissionsCheckboxes(addPermissionsCheckboxes, {}); // Render for "Add User" with all unchecked
        switchTab('list'); // Ensure the list tab is active by default
    });

    // Close main modal
    closeButton.addEventListener('click', () => {
        userManagementModal.style.display = 'none';
    });

    // Close nested modal (edit user)
    closeButtonNested.addEventListener('click', () => {
        editUserModal.style.display = 'none';
    });

    // Close modal by clicking outside content
    window.addEventListener('click', (event) => {
        if (event.target === userManagementModal) {
            userManagementModal.style.display = 'none';
        }
        if (event.target === editUserModal) {
            editUserModal.style.display = 'none';
        }
    });

    // Switch between modal tabs
    modalTabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tab = button.dataset.tab;
            switchTab(tab);
        });
    });

    function switchTab(tabName) {
        modalTabButtons.forEach(button => {
            if (button.dataset.tab === tabName) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });

        tabContents.forEach(content => {
            if (content.id === `${tabName}-tab`) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });
    }

    // --- API Functions for User Management ---

    async function fetchUsers() {
        try {
            const response = await fetch('/api/users', { credentials: 'include' });
            if (!response.ok) {
                if (response.status === 403) {
                    showAlert('You do not have permission to view the user list.');
                }
                throw new Error('Error loading users');
            }
            const data = await response.json();
            if (data.success) {
                return data.users;
            } else {
                showAlert(data.message || 'Unknown error loading users.');
                return [];
            }
        } catch (error) {
            console.error('Error fetching users:', error);
            showAlert('Network error fetching users.');
            return [];
        }
    }

    async function loadUsers() {
        const users = await fetchUsers();
        usersTableBody.innerHTML = ''; // Clear table
        if (users.length === 0) {
            noUsersMessage.style.display = 'block';
            return;
        }
        noUsersMessage.style.display = 'none';

        users.forEach(user => {
            const row = usersTableBody.insertRow();
            row.insertCell().textContent = user.id;
            row.insertCell().textContent = user.username;
            
            // Display permissions in a readable format
            const permissionsCell = row.insertCell();
            const activePermissions = Object.entries(user.permissions)
                                        .filter(([, value]) => value)
                                        .map(([key,]) => allPermissions[key] || key)
                                        .join(', ');
            permissionsCell.textContent = activePermissions || 'None';

            const actionsCell = row.insertCell();
            actionsCell.classList.add('action-buttons-cell');

            const editButton = document.createElement('button');
            editButton.textContent = 'Edit';
            editButton.classList.add('edit-button');
            editButton.addEventListener('click', () => openEditUserModal(user));
            actionsCell.appendChild(editButton);

            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete';
            deleteButton.classList.add('delete-button');
            deleteButton.addEventListener('click', () => deleteUser(user.id, user.username));
            actionsCell.appendChild(deleteButton);
        });
    }

    function renderPermissionsCheckboxes(container, currentPermissions = {}) {
        container.innerHTML = '';
        for (const key in allPermissions) {
            const div = document.createElement('div');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `${container.id}-${key}`;
            checkbox.name = key;
            checkbox.checked = currentPermissions[key] || false; // Check if already has permission

            const label = document.createElement('label');
            label.htmlFor = checkbox.id;
            label.textContent = allPermissions[key];

            div.appendChild(checkbox);
            div.appendChild(label);
            container.appendChild(div);
        }
    }

    // --- Add User ---
    addUserForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        addUserErrorMessage.textContent = '';

        const username = document.getElementById('new-username').value;
        const password = document.getElementById('new-password').value;
        const permissions = {};
        addPermissionsCheckboxes.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            permissions[checkbox.name] = checkbox.checked;
        });

        if (!username || !password) {
            addUserErrorMessage.textContent = 'Username and password are required.';
            return;
        }

        try {
            const response = await fetch('/api/users/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, permissions }),
                credentials: 'include'
            });
            const data = await response.json();
            if (data.success) {
                showAlert(data.message);
                addUserForm.reset(); // Clear the form
                loadUsers(); // Reload user list
                switchTab('list'); // Switch back to list tab
            } else {
                addUserErrorMessage.textContent = data.message || 'Error adding user.';
            }
        } catch (error) {
            console.error('Error adding user:', error);
            addUserErrorMessage.textContent = 'Network error adding user.';
        }
    });

    // --- Edit User ---
    function openEditUserModal(user) {
        editUserIdInput.value = user.id;
        editUsernameTitle.textContent = user.username;
        renderPermissionsCheckboxes(editPermissionsCheckboxes, user.permissions);
        editUserModal.style.display = 'flex'; // Use flex for centering
    }

    editUserForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        editUserErrorMessage.textContent = '';

        const userId = editUserIdInput.value;
        const permissions = {};
        editPermissionsCheckboxes.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            permissions[checkbox.name] = checkbox.checked;
        });

        try {
            const response = await fetch(`/api/users/update_permissions/${userId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ permissions }),
                credentials: 'include'
            });
            const data = await response.json();
            if (data.success) {
                showAlert(data.message);
                editUserModal.style.display = 'none'; // Close the modal
                loadUsers(); // Reload user list
            } else {
                editUserErrorMessage.textContent = data.message || 'Error updating permissions.';
            }
        } catch (error) {
            console.error('Error updating user permissions:', error);
            editUserErrorMessage.textContent = 'Network error updating permissions.';
        }
    });

    // --- Delete User ---
    async function deleteUser(userId, username) {
        // Replace native confirm with custom modal for consistency
        showAlert(`Are you sure you want to delete user "${username}"?`);
        customAlertOkButton.onclick = async () => { // Reassign OK button action
            customAlertModal.style.display = 'none'; // Hide current alert
            try {
                const response = await fetch(`/api/users/delete/${userId}`, {
                    method: 'DELETE',
                    credentials: 'include'
                });
                const data = await response.json();
                if (data.success) {
                    showAlert(data.message);
                    loadUsers(); // Reload the list
                } else {
                    showAlert(data.message || 'Error deleting user.');
                }
            } catch (error) {
                console.error('Error deleting user:', error);
                showAlert('Network error deleting user.');
            }
            customAlertOkButton.onclick = null; // Reset click handler to default
        };
    }

    // --- LOAD INITIAL DASHBOARD DATA ---
    fetch('/api/dashboard-data', {
        method: 'GET',
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
            // If the response is not OK (e.g., 401 Unauthorized), throw an error
            throw new Error('Invalid or expired token. Redirecting...');
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
            
            userPermissions = data.permissions; // Save user permissions
            updateUIBasedOnPermissions(); // Update UI with obtained permissions

        } else {
            // Here we don't use showAlert for the initial redirection, but the native alert
            // so the user understands they must log in.
            // In a production environment, this alert should be a custom modal.
            throw new Error(result.message || 'Error getting dashboard data');
        }
    })
    .catch(error => {
        console.error('Authentication or network error:', error);
        // Show an error message in the UI before redirecting
        // We use a native alert here as it might be an initial load failure.
        alert('Session expired or unauthorized. Please log in again.'); 
        window.location.href = '/'; // Redirect to login if there's a problem
    });


    // --- BUTTON LOGIC ---
    const logoutButton = document.getElementById('logout-button');
    logoutButton.addEventListener('click', async () => {
        try {
            await fetch('/api/logout', {
                method: 'POST',
                credentials: 'include'
            });
        } catch (error) {
            console.error('Error logging out:', error);
        } finally {
            window.location.href = '/'; // Go back to login
        }
    });

    // Power and Multimedia - Now using custom alert
    const shutdownButton = document.querySelector('.action-button.shutdown');
    if (shutdownButton) {
        shutdownButton.addEventListener('click', () => {
            if (userPermissions.shutdown) {
                showAlert('Simulated shutdown command executed.');
            } else {
                showAlert('You do not have permission to shut down the system.');
            }
        });
    }

    const restartButton = document.querySelector('.action-button.restart');
    if (restartButton) {
        restartButton.addEventListener('click', () => {
            if (userPermissions.restart) {
                showAlert('Simulated reboot command executed.');
            } else {
                showAlert('You do not have permission to reboot the system.');
            }
        });
    }

    const lockButton = document.querySelector('.action-button.lock');
    if (lockButton) {
        lockButton.addEventListener('click', () => {
            if (userPermissions.lock) {
                showAlert('Simulated session lock command executed.');
            } else {
                showAlert('You do not have permission to lock the session.');
            }
        });
    }

    const genericPlayPauseButton = document.querySelector('.action-button.play-pause');
    if (genericPlayPauseButton) {
        genericPlayPauseButton.addEventListener('click', () => {
            if (userPermissions.play_pause) {
                showAlert('Simulated Play/Pause command executed.');
            } else {
                showAlert('You do not have permission to control multimedia.');
            }
        });
    }

    // Volume control event listener
    if (volumeSlider) {
        volumeSlider.addEventListener('input', () => {
            if (userPermissions.volume) {
                volumePercentageSpan.textContent = `${volumeSlider.value}%`; // Immediate UI update

                // Clear any existing timer to prevent it from firing
                clearTimeout(volumeChangeTimer); 
                // Set a new timer
                volumeChangeTimer = setTimeout(() => {
                    // This code will execute after 500ms of no further 'input' events
                    showAlert(`Volume changed to: ${volumeSlider.value}% (simulated)`);
                    // Here you would also send the actual API call to the backend:
                    // sendVolumeUpdateToBackend(volumeSlider.value); 
                }, 500); // 500ms debounce time
            } else {
                // Show alert immediately if no permission
                showAlert('You do not have permission to control volume.');
            }
        });
        // Set initial percentage when page loads or permissions update
        volumePercentageSpan.textContent = `${volumeSlider.value}%`;
    }
});

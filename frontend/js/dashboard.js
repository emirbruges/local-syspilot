document.addEventListener('DOMContentLoaded', () => {
    let userPermissions = {}; // Global variable to store user permissions
    let currentOSType = 'Unknown'; // Variable to store the detected OS type
    let allPermissions = { // Definition of all possible permissions
        "shutdown": "Shutdown",
        "restart": "Reboot",
        "lock": "Lock Session",
        "play_pause": "Play/Pause",
        "media_next": "Next Track",
        "media_previous": "Previous Track",
        "volume": "Volume Control",
        "volume_mute": "Mute Volume",
        "system_metrics": "System Metrics",
        "modify_commands": "Modify Commands",
        "manage_users": "Manage Users"
    };

    // --- Modal DOM Elements ---
    const userManagementModal = document.getElementById('user-management-modal');
    const closeUserModalButton = userManagementModal.querySelector('.close-button');
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

    // Custom Alert/Message Modal Elements (retained for confirmations)
    const customAlertModal = document.getElementById('custom-alert-modal');
    const customAlertMessage = document.getElementById('custom-alert-message');
    const customAlertOkButton = document.getElementById('custom-alert-ok-button');
    const closeButtonAlert = customAlertModal.querySelector('.close-button-alert');

    const pageNotification = document.getElementById('page-notification');
    let notificationTimeout;

    // Volume control elements
    const volumeSlider = document.getElementById('volume-slider');
    const volumePercentageSpan = document.getElementById('volume-percentage');
    const volumeMuteButton = document.getElementById('volume-mute-button');
    let volumeChangeTimer;

    // Custom Commands elements
    const customCommandsCard = document.getElementById('custom-commands-card');
    const manageCustomCommandsButton = document.getElementById('manage-custom-commands-button');
    const customCommandsModal = document.getElementById('custom-commands-modal');
    const closeCommandsModalButton = customCommandsModal.querySelector('.close-button');
    const commandListDiv = document.getElementById('command-list');
    const saveCommandsButton = document.getElementById('save-commands-button');
    const resetCommandsButton = document.getElementById('reset-commands-button');
    const commandMessage = document.getElementById('command-message');


    // --- Custom Alert/Message Modal Functions (retained) ---
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

    // --- NEW: In-page Notification Function ---
    function showNotification(message, type = 'info', duration = 3000) {
        clearTimeout(notificationTimeout); // Clear any existing timeout
        pageNotification.textContent = message;
        pageNotification.className = 'page-notification'; // Reset classes
        pageNotification.classList.add('show', type); // Add 'show' and type class (e.g., 'success', 'error')
        
        notificationTimeout = setTimeout(() => {
            pageNotification.classList.remove('show');
        }, duration);
    }


    // --- Function to update UI based on permissions ---
    function updateUIBasedOnPermissions() {
        // Disable power control buttons if no permissions
        document.querySelector('.action-button.shutdown').disabled = !userPermissions.shutdown;
        document.querySelector('.action-button.restart').disabled = !userPermissions.restart;
        document.querySelector('.action-button.lock').disabled = !userPermissions.lock;

        const playPauseButton = document.querySelector('.action-button.play-pause');
        const mediaNextButton = document.querySelector('.action-button.media-next');
        const mediaPreviousButton = document.querySelector('.action-button.media-previous');
        
        if (playPauseButton) {
            playPauseButton.disabled = !userPermissions.play_pause;
        }
        if (mediaNextButton) {
            mediaNextButton.disabled = !userPermissions.media_next;
        }
        if (mediaPreviousButton) {
            mediaPreviousButton.disabled = !userPermissions.media_previous;
        }
        
        // Volume slider, percentage span, and Mute button
        if (volumeSlider) {
            volumeSlider.disabled = !userPermissions.volume;
            if (!userPermissions.volume) {
                volumePercentageSpan.textContent = 'N/A';
            }
        }
        if (volumeMuteButton) {
            volumeMuteButton.disabled = !userPermissions.volume_mute;
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

        // Custom commands card visibility handled directly in the initial fetch
    }

    // --- User Management Modal Functions ---

    // Open user management modal
    manageUsersButton.addEventListener('click', () => {
        userManagementModal.style.display = 'flex';
        loadUsers();
        renderPermissionsCheckboxes(addPermissionsCheckboxes, {});
        switchTab('list');
    });

    // Close main user modal
    closeUserModalButton.addEventListener('click', () => {
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
        if (event.target === customCommandsModal) {
            customCommandsModal.style.display = 'none';
        }
        // Do NOT close customAlertModal here, it needs explicit OK/X click
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
            // Handle specific permission_change flag for 200 OK responses
            if (response.ok) {
                const data = await response.json();
                if (data.permission_change) {
                    showNotification(data.message, 'info'); // Changed to in-page notification
                    // Re-fetch dashboard data to update local permissions (userPermissions)
                    await fetchDashboardData(); 
                    return []; // Return empty so current user list isn't rendered from potentially old token data
                } else if (data.success) {
                    return data.users;
                } else {
                    showNotification(data.message || 'Unknown error loading users.', 'error'); // Changed to in-page notification
                    return [];
                }
            } else {
                // Handle non-200 responses (e.g., 401 Unauthorized)
                if (response.status === 403) {
                    showNotification('You do not have permission to view the user list.', 'error'); // Changed to in-page notification
                }
                throw new Error('Error loading users');
            }
        } catch (error) {
            console.error('Error fetching users:', error);
            showNotification('Network error fetching users.', 'error'); // Changed to in-page notification
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
            if (data.permission_change) { // Handle permission change
                showNotification(data.message, 'info'); // Changed to in-page notification
                await fetchDashboardData();
                return;
            }
            if (data.success) {
                showNotification(data.message, 'success'); // Changed to in-page notification
                addUserForm.reset(); // Clear the form
                loadUsers(); // Reload user list
                switchTab('list'); // Switch back to list tab
            } else {
                addUserErrorMessage.textContent = data.message || 'Error adding user.'; // Keep error message for form context
            }
        } catch (error) {
            console.error('Error adding user:', error);
            addUserErrorMessage.textContent = 'Network error adding user.'; // Keep error message for form context
        }
    });

    // --- Edit User ---
    function openEditUserModal(user) {
        editUserIdInput.value = user.id;
        editUsernameTitle.textContent = user.username;
        renderPermissionsCheckboxes(editPermissionsCheckboxes, user.permissions);
        editUserModal.style.display = 'flex';
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
            if (data.permission_change) { // Handle permission change
                showNotification(data.message, 'info'); // Changed to in-page notification
                await fetchDashboardData(); // Re-fetch dashboard data to update local permissions and UI
                editUserModal.style.display = 'none'; // Close the modal
                loadUsers(); // Reload user list
                return;
            }
            if (data.success) {
                showNotification(data.message, 'success'); // Changed to in-page notification
                editUserModal.style.display = 'none'; // Close the modal
                loadUsers(); // Reload user list
            } else {
                editUserErrorMessage.textContent = data.message || 'Error updating permissions.'; // Keep error message for form context
            }
        } catch (error) {
            console.error('Error updating user permissions:', error);
            editUserErrorMessage.textContent = 'Network error updating permissions.'; // Keep error message for form context
        }
    });

    // --- Delete User ---
    async function deleteUser(userId, username) {
        showAlert(`Are you sure you want to delete user "${username}"?`); // Retained showAlert for confirmation
        customAlertOkButton.onclick = async () => {
            customAlertModal.style.display = 'none';
            try {
                const response = await fetch(`/api/users/delete/${userId}`, {
                    method: 'DELETE',
                    credentials: 'include'
                });
                const data = await response.json();
                if (data.permission_change) { // Handle permission change
                    showNotification(data.message, 'info'); // Changed to in-page notification
                    await fetchDashboardData();
                    return;
                }
                if (data.success) {
                    showNotification(data.message, 'success'); // Changed to in-page notification
                    loadUsers();
                } else {
                    showNotification(data.message || 'Error deleting user.', 'error'); // Changed to in-page notification
                }
            } catch (error) {
                console.error('Error deleting user:', error);
                showNotification('Network error deleting user.', 'error'); // Changed to in-page notification
            }
            customAlertOkButton.onclick = null; // Reset click handler to default
        };
    }

    // --- Custom Commands Modal Functions ---

    // Open custom commands modal
    manageCustomCommandsButton.addEventListener('click', () => {
        customCommandsModal.style.display = 'flex';
        loadCustomCommands();
    });

    // Close custom commands modal
    closeCommandsModalButton.addEventListener('click', () => {
        customCommandsModal.style.display = 'none';
        commandMessage.textContent = '';
        commandMessage.style.display = 'none';
    });

    async function fetchCustomCommands() {
        try {
            const response = await fetch('/api/commands', { credentials: 'include' });
            // Handle specific permission_change flag for 200 OK responses
            if (response.ok) {
                const data = await response.json();
                if (data.permission_change) {
                    showNotification(data.message, 'info'); // Changed to in-page notification
                    await fetchDashboardData(); // Update local permissions
                    return {}; // Return empty so commands aren't rendered from potentially old token data
                } else if (data.success) {
                    return data.commands;
                } else {
                    showNotification(data.message || 'Unknown error loading commands.', 'error'); // Changed to in-page notification
                    return {};
                }
            } else {
                // Handle non-200 responses (e.g., 401 Unauthorized)
                if (response.status === 403) {
                    showNotification('You do not have permission to view/modify commands.', 'error'); // Changed to in-page notification
                }
                throw new Error('Error loading commands');
            }
        } catch (error) {
            console.error('Error fetching commands:', error);
            showNotification('Network error fetching commands.', 'error'); // Changed to in-page notification
            return {};
        }
    }

    async function loadCustomCommands() {
        commandMessage.style.display = 'none';
        commandListDiv.innerHTML = '<p style="text-align:center;">Loading commands...</p>';
        const commands = await fetchCustomCommands();
        commandListDiv.innerHTML = '';

        if (Object.keys(commands).length === 0) {
            commandListDiv.innerHTML = '<p style="text-align:center;">No custom commands defined yet. Using defaults.</p>';
            return;
        }

        const commandNames = {
            "shutdown_cmd": "Shutdown Command",
            "restart_cmd": "Reboot Command",
            "lock_cmd": "Lock Session Command",
            "play_pause_cmd": "Play/Pause Command",
            "media_next_cmd": "Media Next Command",
            "media_previous_cmd": "Media Previous Command",
            "set_volume_cmd": "Set Volume Command",
            "get_volume_cmd": "Get Volume Command",
            "volume_mute_cmd": "Mute Volume Command",
            "get_mute_status_cmd": "Get Mute Status Command",
            "get_cpu_usage_cmd": "Get CPU Usage Command",
            "get_ram_usage_cmd": "Get RAM Usage Command",
            "get_uptime_cmd": "Get Uptime Command"
        };

        const sortedCommandKeys = Object.keys(commands).sort((a, b) => {
            const nameA = commandNames[a] || a;
            const nameB = commandNames[b] || b;
            return nameA.localeCompare(nameB);
        });


        sortedCommandKeys.forEach(key => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('command-item');

            const label = document.createElement('label');
            label.textContent = commandNames[key] || key.replace(/_/g, ' ').replace('cmd', '').trim().split(' ').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' '); 
            label.htmlFor = `command-${key}`;

            const input = document.createElement('input');
            input.type = 'text';
            input.id = `command-${key}`;
            input.name = key;
            input.value = commands[key];
            input.placeholder = `Enter command for ${label.textContent.toLowerCase()}`;

            itemDiv.appendChild(label);
            itemDiv.appendChild(input);
            commandListDiv.appendChild(itemDiv);
        });
    }

    saveCommandsButton.addEventListener('click', async () => {
        commandMessage.textContent = '';
        commandMessage.style.display = 'none';
        const updatedCommands = {};
        commandListDiv.querySelectorAll('.command-item input[type="text"]').forEach(input => {
            updatedCommands[input.name] = input.value.trim();
        });

        try {
            const response = await fetch('/api/commands/update', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ commands: updatedCommands }),
                credentials: 'include'
            });
            const data = await response.json();
            if (data.permission_change) { // Handle permission change
                showNotification(data.message, 'info'); // Changed to in-page notification
                await fetchDashboardData();
                return;
            }
            if (data.success) {
                showNotification(data.message || 'Commands saved successfully!', 'success'); // Changed to in-page notification
                // commandMessage.style.color = 'var(--rose-pine-pine)'; // No longer needed for in-page notification
                // commandMessage.style.display = 'block';
            } else {
                commandMessage.textContent = data.message || 'Error saving commands.'; // Keep for form context
                commandMessage.style.color = 'var(--rose-pine-love)';
                commandMessage.style.display = 'block';
            }
        } catch (error) {
            console.error('Error saving commands:', error);
            commandMessage.textContent = 'Network error saving commands.'; // Keep for form context
            commandMessage.style.color = 'var(--rose-pine-love)';
            commandMessage.style.display = 'block';
        }
    });

    resetCommandsButton.addEventListener('click', async () => {
        showAlert('Are you sure you want to reset all commands to their default values? This cannot be undone.'); // Retained showAlert for confirmation
        customAlertOkButton.onclick = async () => {
            customAlertModal.style.display = 'none';
            commandMessage.textContent = '';
            commandMessage.style.display = 'none';
            try {
                const response = await fetch('/api/commands/reset', {
                    method: 'POST',
                    credentials: 'include'
                });
                const data = await response.json();
                if (data.permission_change) { // Handle permission change
                    showNotification(data.message, 'info'); // Changed to in-page notification
                    await fetchDashboardData();
                    return;
                }
                if (data.success) {
                    showNotification(data.message || 'Commands reset to defaults successfully!', 'success'); // Changed to in-page notification
                    // commandMessage.style.color = 'var(--rose-pine-pine)'; // No longer needed
                    // commandMessage.style.display = 'block';
                    loadCustomCommands();
                } else {
                    commandMessage.textContent = data.message || 'Error resetting commands.'; // Keep for form context
                    commandMessage.style.color = 'var(--rose-pine-love)';
                    commandMessage.style.display = 'block';
                }
            } catch (error) {
                console.error('Error resetting commands:', error);
                commandMessage.textContent = 'Network error resetting commands.'; // Keep for form context
                commandMessage.style.color = 'var(--rose-pine-love)';
                commandMessage.style.display = 'block';
            }
            customAlertOkButton.onclick = null;
        };
    });


    // --- Function to fetch and update Dashboard Data ---
    async function fetchDashboardData() {
        try {
            const response = await fetch('/api/dashboard-data', {
                method: 'GET',
                credentials: 'include'
            });
            
            // Handle HTTP errors (e.g., 401 Unauthorized)
            if (!response.ok) {
                console.error('Session expired or unauthorized. Forcing re-login.');
                showAlert('Session expired or unauthorized. Please log in again.');
                window.location.href = '/';
                return; // Stop execution
            }
            
            const result = await response.json();
            
            if (result.permission_change) { // Special case for permission changes
                showNotification(result.message, 'info'); // Use in-page notification
                // No recursive fetchDashboardData() here.
                // The new token is already set by the backend.
                // The next block will update userPermissions and UI based on this new state.
            }

            if (result.success && result.data !== undefined) { // Check result.data explicitly
                const data = result.data;
                document.getElementById('cpu-usage').textContent = data.cpu_usage;
                document.getElementById('ram-usage').textContent = data.ram_usage;
                document.getElementById('uptime').textContent = data.uptime;
                document.getElementById('welcome-message').textContent = `Welcome, ${data.user}`;
                
                userPermissions = data.permissions; // Update global userPermissions with fresh data
                currentOSType = data.os_type;
                
                if (currentOSType === 'Linux' && userPermissions.modify_commands) {
                    customCommandsCard.style.display = 'block';
                } else {
                    customCommandsCard.style.display = 'none';
                }

                updateUIBasedOnPermissions(); // Update UI based on potentially new userPermissions

            } else if (!result.success) { // Handle generic backend success=false but not permission_change
                showAlert('Error getting dashboard data: ' + (result.message || 'Unknown'));
                window.location.href = '/';
            }
        } catch (error) {
            console.error('Network error loading dashboard data:', error);
            showAlert('Connection error. Please refresh the page or try again later.');
        }
    }

    // --- Function to fetch and update current system volume and mute status ---
    async function getAndUpdateVolume() {
        if ((!userPermissions.volume && !userPermissions.volume_mute) || currentOSType !== 'Linux') {
            volumePercentageSpan.textContent = 'N/A';
            volumeSlider.disabled = true;
            volumeMuteButton.disabled = true;
            return;
        }

        try {
            const response = await fetch('/api/volume', {
                method: 'GET',
                credentials: 'include'
            });
            // Handle permission_change flag for 200 OK responses
            if (!response.ok) {
                 // This means a 401 Unauthorized from token_required (invalid/expired token or user not found)
                console.error('Session expired or unauthorized for volume. Forcing re-login.');
                showAlert('Session expired or unauthorized. Please log in again.');
                window.location.href = '/';
                return;
            }
            
            const data = await response.json();

            if (data.permission_change) { // Special case for permission changes
                showNotification(data.message, 'info'); // Changed to in-page notification
                await fetchDashboardData(); // Reload to update userPermissions and UI
                return;
            }

            if (data.success) {
                if (data.level !== undefined) {
                    volumeSlider.value = data.level;
                    volumePercentageSpan.textContent = `${data.level}%`;
                } else {
                    volumePercentageSpan.textContent = `N/A`;
                }

                if (data.is_muted !== undefined) {
                    updateVolumeSliderState(data.is_muted);
                }
            } else {
                console.warn('Backend /api/volume did not return valid data or failed:', data.message || 'Unknown error.');
                volumePercentageSpan.textContent = `Error`;
                volumeSlider.disabled = true;
                volumeMuteButton.disabled = true;
            }
        } catch (error) {
            console.error('Error fetching current volume:', error);
            volumePercentageSpan.textContent = `Error`;
            volumeSlider.disabled = true;
            volumeMuteButton.disabled = true;
        }
    }

    // NEW FUNCTION: Update the visual state of the volume slider and mute button
    function updateVolumeSliderState(isMuted) {
        if (isMuted) {
            volumeSlider.disabled = true; // Disable slider if muted
            volumeMuteButton.classList.add('active-mute');
            volumeMuteButton.textContent = '🔊 Unmute'; // Change text to 'Unmute'
        } else {
            // Only re-enable if the user *has* the volume permission
            volumeSlider.disabled = !userPermissions.volume;
            volumeMuteButton.classList.remove('active-mute');
            volumeMuteButton.textContent = '🔇 Mute'; // Change text to 'Mute'
        }
    }


    // --- Initial Load and Periodic Updates ---
    let dashboardDataInterval;
    let volumeRefreshTimer;

    // Initial load sequence (similar to previous, but now includes permission_change check)
    fetchDashboardData()
    .then(() => {
        // Start periodic updates after initial data load is successful
        if (dashboardDataInterval) clearInterval(dashboardDataInterval);
        dashboardDataInterval = setInterval(fetchDashboardData, 5000);

        if (volumeRefreshTimer) clearInterval(volumeRefreshTimer);
        // Start volume and mute status check only if permissions allow
        if (currentOSType === 'Linux' && (userPermissions.volume || userPermissions.volume_mute)) {
            getAndUpdateVolume(); // Initial call for volume and mute status
            volumeRefreshTimer = setInterval(getAndUpdateVolume, 5000);
        } else {
            volumePercentageSpan.textContent = 'N/A';
            volumeSlider.disabled = true;
            volumeMuteButton.disabled = true;
        }
    })
    .catch(error => {
        // This catch handles critical errors during the initial fetchDashboardData itself
        console.error('Critical error loading dashboard:', error);
        // Redirection should be handled by fetchDashboardData's internal logic for 401
    });


    // --- BUTTON LOGIC ---
    const logoutButton = document.getElementById('logout-button');
    logoutButton.addEventListener('click', async () => {
        showAlert('Are you sure you want to log out?'); // Retained showAlert for confirmation
        customAlertOkButton.onclick = async () => {
            customAlertModal.style.display = 'none';
            try {
                await fetch('/api/logout', {
                    method: 'POST',
                    credentials: 'include'
                });
            } catch (error) {
                console.error('Error logging out:', error);
            } finally {
                // Clear all intervals on logout
                if (dashboardDataInterval) clearInterval(dashboardDataInterval);
                if (volumeRefreshTimer) clearInterval(volumeRefreshTimer);
                window.location.href = '/'; // Go back to login
            }
            customAlertOkButton.onclick = null; // Reset click handler to default
        };
    });

    // Helper function for action buttons to avoid code repetition
    async function handleActionButtonClick(permissionKey, endpoint, body = null) {
        if (userPermissions[permissionKey]) {
            // Confirmations for critical actions
            const confirmActions = ['shutdown', 'restart', 'lock'];
            if (confirmActions.includes(permissionKey)) {
                let actionName = allPermissions[permissionKey] || permissionKey;
                showAlert(`Are you sure you want to ${actionName.toLowerCase()} the system?`);
                customAlertOkButton.onclick = async () => {
                    customAlertModal.style.display = 'none';
                    await executeAction(permissionKey, endpoint, body);
                    customAlertOkButton.onclick = null; // Reset handler
                };
            } else {
                await executeAction(permissionKey, endpoint, body);
            }
        } else {
            showNotification(`You do not have permission to ${allPermissions[permissionKey].toLowerCase()}.`, 'error'); // Changed to in-page notification
        }
    }

    async function executeAction(permissionKey, endpoint, body = null) {
        try {
            const fetchOptions = {
                method: 'POST',
                credentials: 'include'
            };
            if (body) {
                fetchOptions.headers = { 'Content-Type': 'application/json' };
                fetchOptions.body = JSON.stringify(body);
            }
            const response = await fetch(endpoint, fetchOptions);
            const data = await response.json();

            if (data.permission_change) {
                showNotification(data.message, 'info'); // Changed to in-page notification
                await fetchDashboardData(); // Update local permissions and UI
                return; // Stop execution, new state will be reflected
            }

            showNotification(data.message, data.success ? 'success' : 'error'); // Changed to in-page notification, add type
            if (permissionKey === 'volume_mute' || permissionKey === 'volume') {
                getAndUpdateVolume(); // Immediate update after volume actions
            }
        } catch (error) {
            console.error(`Error calling ${endpoint} API:`, error);
            showNotification('Network error or server issue.', 'error'); // Changed to in-page notification
        }
    }


    // Attach event listeners using the helper function
    document.querySelector('.action-button.shutdown').addEventListener('click', () => handleActionButtonClick('shutdown', '/api/action/shutdown'));
    document.querySelector('.action-button.restart').addEventListener('click', () => handleActionButtonClick('restart', '/api/action/restart'));
    document.querySelector('.action-button.lock').addEventListener('click', () => handleActionButtonClick('lock', '/api/action/lock'));
    document.querySelector('.action-button.play-pause').addEventListener('click', () => handleActionButtonClick('play_pause', '/api/action/play_pause'));
    document.querySelector('.action-button.media-next').addEventListener('click', () => handleActionButtonClick('media_next', '/api/action/media_next'));
    document.querySelector('.action-button.media-previous').addEventListener('click', () => handleActionButtonClick('media_previous', '/api/action/media_previous'));
    volumeMuteButton.addEventListener('click', () => handleActionButtonClick('volume_mute', '/api/action/volume_mute'));


    // Volume control event listener with debounce
    if (volumeSlider) {
        volumeSlider.addEventListener('input', () => {
            if (userPermissions.volume) {
                volumePercentageSpan.textContent = `${volumeSlider.value}%`; // Immediate UI update

                clearTimeout(volumeChangeTimer);
                volumeChangeTimer = setTimeout(async () => {
                    // showNotification(`Volume changed to: ${volumeSlider.value}%`, 'info'); // This might be too frequent, optional
                    try {
                        const response = await fetch('/api/action/set_volume', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ level: parseInt(volumeSlider.value) }),
                            credentials: 'include'
                        });
                        const data = await response.json();
                        if (data.permission_change) { // Handle permission change
                            showNotification(data.message, 'info'); // Changed to in-page notification
                            await fetchDashboardData();
                            return;
                        }
                        if (data.success) {
                            showNotification(`Volume changed to: ${volumeSlider.value}%`, 'success'); // Show success message
                        } else {
                            showNotification(`Failed to set volume: ${data.message}`, 'error');
                        }
                        getAndUpdateVolume(); // Call for instant feedback on mute status
                    } catch (error) {
                        console.error('Error setting volume via API:', error);
                        showNotification('Network error setting volume.', 'error'); // Changed to in-page notification
                    }
                }, 500); // 500ms debounce time
            } else {
                // This should not happen if slider is disabled by updateUIBasedOnPermissions
                showNotification('You do not have permission to control volume.', 'error'); // Changed to in-page notification
            }
        });
    }

    // --- Global ESC key listener for modals ---
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            if (editUserModal.style.display === 'flex') {
                editUserModal.style.display = 'none';
            } else if (customCommandsModal.style.display === 'flex') {
                customCommandsModal.style.display = 'none';
                commandMessage.textContent = '';
                commandMessage.style.display = 'none';
            } else if (userManagementModal.style.display === 'flex') {
                userManagementModal.style.display = 'none';
            } else if (customAlertModal.style.display === 'flex') {
                customAlertModal.style.display = 'none'; 
            }

            if (pageNotification.classList.contains('show')) {
                pageNotification.classList.remove('show');
            }
        }
    });

});


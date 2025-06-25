document.addEventListener('DOMContentLoaded', () => {
    let userPermissions = {}; // Global variable to store user permissions
    let currentOSType = 'Unknown'; // Variable to store the detected OS type
    let allPermissions = { // Definition of all possible permissions
        "shutdown": "Shutdown",
        "restart": "Reboot",
        "lock": "Lock Session",
        "play_pause": "Play/Pause",
        "volume": "Volume Control",
        "system_metrics": "System Metrics",
        "modify_commands": "Modify Commands",
        "manage_users": "Manage Users"
    };

    // --- Modal DOM Elements ---
    const userManagementModal = document.getElementById('user-management-modal');
    const closeUserModalButton = userManagementModal.querySelector('.close-button'); // Renamed for clarity
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

    // Volume control elements
    const volumeSlider = document.getElementById('volume-slider');
    const volumePercentageSpan = document.getElementById('volume-percentage');
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
        if (volumeSlider) {
            volumeSlider.disabled = !userPermissions.volume;
            // The volume percentage will be updated by the getAndUpdateVolume interval,
            // but for initial display if permissions change, ensure it's set.
            // If volume is disabled, set to N/A.
            if (!userPermissions.volume) {
                volumePercentageSpan.textContent = 'N/A';
            }
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
        userManagementModal.style.display = 'flex'; // Use flex for centering
        loadUsers(); // Load user list when opening the modal
        renderPermissionsCheckboxes(addPermissionsCheckboxes, {}); // Render for "Add User" with all unchecked
        switchTab('list'); // Ensure the list tab is active by default
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
        if (event.target === customCommandsModal) { // Also close commands modal
            customCommandsModal.style.display = 'none';
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
        showAlert(`Are you sure you want to delete user "${username}"?`);
        customAlertOkButton.onclick = async () => {
            customAlertModal.style.display = 'none';
            try {
                const response = await fetch(`/api/users/delete/${userId}`, {
                    method: 'DELETE',
                    credentials: 'include'
                });
                const data = await response.json();
                if (data.success) {
                    showAlert(data.message);
                    loadUsers();
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

    // --- Custom Commands Modal Functions ---

    // Open custom commands modal
    manageCustomCommandsButton.addEventListener('click', () => {
        customCommandsModal.style.display = 'flex';
        loadCustomCommands();
    });

    // Close custom commands modal
    closeCommandsModalButton.addEventListener('click', () => {
        customCommandsModal.style.display = 'none';
        commandMessage.textContent = ''; // Clear any messages
        commandMessage.style.display = 'none'; // Ensure it's hidden
    });

    async function fetchCustomCommands() {
        try {
            const response = await fetch('/api/commands', { credentials: 'include' });
            if (!response.ok) {
                if (response.status === 403) {
                    showAlert('You do not have permission to view/modify commands.');
                }
                throw new Error('Error loading commands');
            }
            const data = await response.json();
            if (data.success) {
                return data.commands;
            } else {
                showAlert(data.message || 'Unknown error loading commands.');
                return {};
            }
        } catch (error) {
            console.error('Error fetching commands:', error);
            showAlert('Network error fetching commands.');
            return {};
        }
    }

    async function loadCustomCommands() {
        commandMessage.style.display = 'none'; // Hide message when loading new commands
        commandListDiv.innerHTML = '<p style="text-align:center;">Loading commands...</p>';
        const commands = await fetchCustomCommands();
        commandListDiv.innerHTML = ''; // Clear loading message

        if (Object.keys(commands).length === 0) {
            commandListDiv.innerHTML = '<p style="text-align:center;">No custom commands defined yet. Using defaults.</p>';
            return;
        }

        // Mapping from command key to a more user-friendly name (can be reused from allPermissions or defined separately)
        const commandNames = {
            "shutdown_cmd": "Shutdown Command",
            "restart_cmd": "Reboot Command",
            "lock_cmd": "Lock Session Command",
            "play_pause_cmd": "Play/Pause Command",
            "set_volume_cmd": "Set Volume Command",
            "get_volume_cmd": "Get Volume Command",
            "get_cpu_usage_cmd": "Get CPU Usage Command",
            "get_ram_usage_cmd": "Get RAM Usage Command",
            "get_uptime_cmd": "Get Uptime Command"
        };

        // Sort commands by their friendly name for consistent display
        const sortedCommandKeys = Object.keys(commands).sort((a, b) => {
            const nameA = commandNames[a] || a;
            const nameB = commandNames[b] || b;
            return nameA.localeCompare(nameB);
        });


        sortedCommandKeys.forEach(key => {
            const itemDiv = document.createElement('div');
            itemDiv.classList.add('command-item');

            const label = document.createElement('label');
            // Use the predefined name or format the key if not found
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
        commandMessage.style.display = 'none'; // Hide message initially
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
            if (data.success) {
                commandMessage.textContent = data.message || 'Commands saved successfully!';
                commandMessage.style.color = 'var(--rose-pine-pine)';
                commandMessage.style.display = 'block'; // Show message
            } else {
                commandMessage.textContent = data.message || 'Error saving commands.';
                commandMessage.style.color = 'var(--rose-pine-love)';
                commandMessage.style.display = 'block'; // Show message
            }
        } catch (error) {
            console.error('Error saving commands:', error);
            commandMessage.textContent = 'Network error saving commands.';
            commandMessage.style.color = 'var(--rose-pine-love)';
            commandMessage.style.display = 'block'; // Show message
        }
    });

    resetCommandsButton.addEventListener('click', async () => {
        showAlert('Are you sure you want to reset all commands to their default values? This cannot be undone.');
        customAlertOkButton.onclick = async () => {
            customAlertModal.style.display = 'none';
            commandMessage.textContent = '';
            commandMessage.style.display = 'none'; // Hide message initially
            try {
                const response = await fetch('/api/commands/reset', {
                    method: 'POST',
                    credentials: 'include'
                });
                const data = await response.json();
                if (data.success) {
                    commandMessage.textContent = data.message || 'Commands reset to defaults successfully!';
                    commandMessage.style.color = 'var(--rose-pine-pine)';
                    commandMessage.style.display = 'block'; // Show message
                    loadCustomCommands(); // Reload commands to show defaults
                } else {
                    commandMessage.textContent = data.message || 'Error resetting commands.';
                    commandMessage.style.color = 'var(--rose-pine-love)';
                    commandMessage.style.display = 'block'; // Show message
                }
            } catch (error) {
                console.error('Error resetting commands:', error);
                commandMessage.textContent = 'Network error resetting commands.';
                commandMessage.style.color = 'var(--rose-pine-love)';
                commandMessage.style.display = 'block'; // Show message
            }
            customAlertOkButton.onclick = null; // Reset click handler to default
        };
    });


    // --- Function to fetch and update Dashboard Data ---
    async function fetchDashboardData() {
        try {
            const response = await fetch('/api/dashboard-data', {
                method: 'GET',
                credentials: 'include'
            });
            if (!response.ok) {
                throw new Error('Invalid or expired token. Redirecting...');
            }
            const result = await response.json();
            if (result.success) {
                const data = result.data;
                document.getElementById('cpu-usage').textContent = data.cpu_usage;
                document.getElementById('ram-usage').textContent = data.ram_usage;
                document.getElementById('uptime').textContent = data.uptime;
                document.getElementById('welcome-message').textContent = `Welcome, ${data.user}`;
                
                userPermissions = data.permissions;
                currentOSType = data.os_type;
                
                if (currentOSType === 'Linux' && userPermissions.modify_commands) {
                    customCommandsCard.style.display = 'block';
                } else {
                    customCommandsCard.style.display = 'none';
                }

                updateUIBasedOnPermissions();

            } else {
                alert('Session expired or unauthorized. Please log in again.'); 
                window.location.href = '/';
            }
        } catch (error) {
            console.error('Authentication or network error:', error);
            alert('Session expired or unauthorized. Please log in again.'); 
            window.location.href = '/';
        }
    }

    // --- Function to fetch and update current system volume ---
    async function getAndUpdateVolume() {
        // Only attempt to fetch if user has volume permission AND we're on Linux
        if (!userPermissions.volume || currentOSType !== 'Linux') {
            volumePercentageSpan.textContent = 'N/A';
            return;
        }

        try {
            const response = await fetch('/api/volume', {
                method: 'GET',
                credentials: 'include'
            });
            const data = await response.json();
            if (data.success && data.level !== undefined) {
                volumeSlider.value = data.level; // Update slider position
                volumePercentageSpan.textContent = `${data.level}%`;
            } else {
                console.warn('Backend /api/volume did not return a valid level or failed:', data.message || 'Unknown error.');
                volumePercentageSpan.textContent = `Error`; // Indicate an error in fetching
            }
        } catch (error) {
            console.error('Error fetching current volume:', error);
            volumePercentageSpan.textContent = `Error`; // Indicate an error
        }
    }


    // --- Initial Load and Periodic Updates ---
    let dashboardDataInterval;
    let volumeRefreshTimer;

    fetch('/api/dashboard-data', {
        method: 'GET',
        credentials: 'include'
    })
    .then(response => {
        if (!response.ok) {
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
            
            userPermissions = data.permissions;
            currentOSType = data.os_type;
            
            // Manage custom commands card visibility
            if (currentOSType === 'Linux' && userPermissions.modify_commands) {
                customCommandsCard.style.display = 'block';
            } else {
                customCommandsCard.style.display = 'none';
            }

            updateUIBasedOnPermissions(); // Update other UI elements

            // Start periodic updates after initial data load
            if (dashboardDataInterval) clearInterval(dashboardDataInterval);
            dashboardDataInterval = setInterval(fetchDashboardData, 5000);

            if (volumeRefreshTimer) clearInterval(volumeRefreshTimer);
            if (currentOSType === 'Linux' && userPermissions.volume) {
                getAndUpdateVolume(); // Initial call for volume
                volumeRefreshTimer = setInterval(getAndUpdateVolume, 5000);
            } else {
                volumePercentageSpan.textContent = 'N/A'; // Clear volume if not applicable
            }

        } else {
            alert('Session expired or unauthorized. Please log in again.'); 
            window.location.href = '/';
        }
    })
    .catch(error => {
        console.error('Authentication or network error:', error);
        alert('Session expired or unauthorized. Please log in again.'); 
        window.location.href = '/';
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
            // Clear all intervals on logout
            if (dashboardDataInterval) clearInterval(dashboardDataInterval);
            if (volumeRefreshTimer) clearInterval(volumeRefreshTimer);
            window.location.href = '/'; // Go back to login
        }
    });

    // Power and Multimedia - Now using custom alert
    const shutdownButton = document.querySelector('.action-button.shutdown');
    if (shutdownButton) {
        shutdownButton.addEventListener('click', async () => {
            if (userPermissions.shutdown) {
                try {
                    const response = await fetch('/api/action/shutdown', {
                        method: 'POST',
                        credentials: 'include'
                    });
                    const data = await response.json();
                    showAlert(data.message);
                } catch (error) {
                    console.error('Error calling shutdown API:', error);
                    showAlert('Network error calling shutdown API.');
                }
            } else {
                showAlert('You do not have permission to shut down the system.');
            }
        });
    }

    const restartButton = document.querySelector('.action-button.restart');
    if (restartButton) {
        restartButton.addEventListener('click', async () => {
            if (userPermissions.restart) {
                try {
                    const response = await fetch('/api/action/restart', {
                        method: 'POST',
                        credentials: 'include'
                    });
                    const data = await response.json();
                    showAlert(data.message);
                } catch (error) {
                    console.error('Error calling restart API:', error);
                    showAlert('Network error calling restart API.');
                }
            } else {
                showAlert('You do not have permission to reboot the system.');
            }
        });
    }

    const lockButton = document.querySelector('.action-button.lock');
    if (lockButton) {
        lockButton.addEventListener('click', async () => {
            if (userPermissions.lock) {
                try {
                    const response = await fetch('/api/action/lock', {
                        method: 'POST',
                        credentials: 'include'
                    });
                    const data = await response.json();
                    showAlert(data.message);
                } catch (error) {
                    console.error('Error calling lock API:', error);
                    showAlert('Network error calling lock API.');
                }
            } else {
                showAlert('You do not have permission to lock the session.');
            }
        });
    }

    const genericPlayPauseButton = document.querySelector('.action-button.play-pause');
    if (genericPlayPauseButton) {
        genericPlayPauseButton.addEventListener('click', async () => {
            if (userPermissions.play_pause) {
                try {
                    const response = await fetch('/api/action/play_pause', {
                        method: 'POST',
                        credentials: 'include'
                    });
                    const data = await response.json();
                    showAlert(data.message);
                } catch (error) {
                    console.error('Error calling play/pause API:', error);
                    showAlert('Network error calling play/pause API.');
                }
            } else {
                showAlert('You do not have permission to control multimedia.');
            }
        });
    }

    // Volume control event listener with debounce
    if (volumeSlider) {
        volumeSlider.addEventListener('input', () => {
            if (userPermissions.volume) {
                volumePercentageSpan.textContent = `${volumeSlider.value}%`; // Immediate UI update

                clearTimeout(volumeChangeTimer);
                volumeChangeTimer = setTimeout(async () => {
                    showAlert(`Volume changed to: ${volumeSlider.value}%`);
                    try {
                        const response = await fetch('/api/action/set_volume', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ level: parseInt(volumeSlider.value) }),
                            credentials: 'include'
                        });
                        const data = await response.json();
                        if (!data.success) {
                            showAlert(`Failed to set volume: ${data.message}`);
                        }
                        // After setting, immediately request the updated volume to sync UI with system
                        getAndUpdateVolume(); 
                    } catch (error) {
                        console.error('Error setting volume via API:', error);
                        showAlert('Network error setting volume.');
                    }
                }, 500); // 500ms debounce time
            } else {
                showAlert('You do not have permission to control volume.');
            }
        });
        // Initial percentage will be set by getAndUpdateVolume or N/A
    }

    // --- Global ESC key listener for modals ---
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            // Prioritize closing the innermost/topmost modal first
            if (editUserModal.style.display === 'flex') {
                editUserModal.style.display = 'none';
            } else if (customCommandsModal.style.display === 'flex') {
                customCommandsModal.style.display = 'none';
                commandMessage.textContent = ''; // Clear message on close
                commandMessage.style.display = 'none'; // Hide message
            } else if (userManagementModal.style.display === 'flex') {
                userManagementModal.style.display = 'none';
            } else if (customAlertModal.style.display === 'flex') {
                customAlertModal.style.display = 'none';
            }
        }
    });

});

import platform
from dotenv import load_dotenv
import os
import sqlite3
from flask import Flask, request, jsonify, make_response, render_template, send_from_directory, redirect, url_for
from flask_cors import CORS
import jwt
import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import json

supported_system = False
sys_actions = None
if platform.system() == "Linux":
    from system_actions import linux_actions as sys_actions
    print("Running on Linux. Using linux_actions.")
    supported_system = True
elif platform.system() == "Windows":
    from system_actions import windows_actions as sys_actions
    print("Running on Windows. Using windows_actions.")
    supported_system = True
else:
    print("System not supported, please use Linux or Windows.")

load_dotenv() # Loads .env or settings.ini variables

# --- APP CONFIGURATION ---
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app = Flask(
    __name__,
    template_folder=frontend_path,
    static_folder=os.path.join(frontend_path)
    )

CORS(app)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

default_admin_username = os.getenv("DEFAULT_USERNAME")
default_admin_password = os.getenv("DEFAULT_PASSWORD")
database_filename = os.getenv("DATABASE_FILENAME", 'syspilot.db')

# --- DATABASE CONFIGURATION ---
DATABASE = os.path.join(os.path.dirname(__file__), database_filename)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database, creates the users and commands tables if they don't exist,
    and populates them with default values if empty.
    """
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                permissions TEXT NOT NULL
            )
        ''')
        conn.commit()

        # Create commands table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                command_key TEXT PRIMARY KEY NOT NULL,
                command_value TEXT NOT NULL
            )
        ''')
        conn.commit()

        # Populate default admin user if none exists
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            print("No users found. Creating default administrator user...")
            username_to_create = default_admin_username if default_admin_username else "admin"
            password_to_create = default_admin_password if default_admin_password else "admin123" 

            hashed_password = generate_password_hash(password_to_create)
            default_permissions = {
                "shutdown": True, "restart": True, "lock": True,
                "play_pause": True, "volume": True, "system_metrics": True,
                "modify_commands": True, "manage_users": True
            }
            permissions_json = json.dumps(default_permissions)

            try:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, permissions) VALUES (?, ?, ?)",
                    (username_to_create, hashed_password, permissions_json)
                )
                conn.commit()
                print(f"Default administrator user '{username_to_create}' created with default password.")
            except sqlite3.IntegrityError:
                print(f"The user '{username_to_create}' already exists.")
        
        # Populate default commands if commands table is empty
        cursor.execute("SELECT COUNT(*) FROM commands")
        if cursor.fetchone()[0] == 0 and supported_system:
            print("No custom commands found. Populating with system defaults...")
            if sys_actions and hasattr(sys_actions, 'DEFAULT_COMMANDS'):
                for key, value in sys_actions.DEFAULT_COMMANDS.items():
                    try:
                        cursor.execute(
                            "INSERT INTO commands (command_key, command_value) VALUES (?, ?)",
                            (key, value)
                        )
                    except sqlite3.IntegrityError:
                        print(f"Command key '{key}' already exists, skipping default insertion.")
                conn.commit()
                print("Default commands populated successfully.")
            else:
                print("Cannot populate default commands: sys_actions.DEFAULT_COMMANDS not found or system not supported.")
        conn.close()

# Ensure the database is initialized when the application starts
with app.app_context():
    init_db()


def token_required(f):
    """
    Decorator to protect routes, verifying the JWT token in cookies.
    Redirects to login if the token is invalid or missing.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('syspilot_token')
        if not token:
            print("Token not found in cookies. Redirecting to /")
            return redirect('/')
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['user']
            current_permissions = data.get('permissions', {})
            return f(current_user, current_permissions, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            print("Token expired. Redirecting to /")
            return redirect('/')
        except jwt.InvalidTokenError:
            print("Invalid token. Redirecting to /")
            return redirect('/')
    return decorated

# --- HTML ROUTES ---
@app.route('/')
def index():
    token = request.cookies.get('syspilot_token')
    if token:
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            return redirect(url_for('dashboard'))
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass

    return render_template('index.html')

@app.route('/index.html')
@app.route('/dashboard.html')
def redirect_to_root_or_dashboard():
    """Redirects direct requests to index.html or dashboard.html."""
    token = request.cookies.get('syspilot_token')
    if token:
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            return redirect(url_for('dashboard'))
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass
    return redirect(url_for('index'))


@app.route('/dashboard')
@token_required
def dashboard(current_user, current_permissions):
    """Renders the dashboard if the user is authenticated."""
    return render_template('dashboard.html')

# --- API ROUTES ---
@app.route('/api/login', methods=['POST'])
def login():
    """Handles user login."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        permissions = json.loads(user['permissions'])

        token = jwt.encode({
            'user': username,
            'permissions': permissions,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, app.config['SECRET_KEY'], algorithm="HS256")

        response = make_response(jsonify({'success': True, 'message': 'Login successful'}))
        response.set_cookie('syspilot_token', token, httponly=True, samesite='Lax')
        return response
    
    return jsonify({'success': False, 'message': 'Incorrect credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logs out the user by deleting the cookie."""
    response = make_response(jsonify({'success': True, 'message': 'Logged out successfully'}))
    response.set_cookie('syspilot_token', '', expires=0, httponly=True, samesite='Lax')
    return response

@app.route('/api/dashboard-data')
@token_required
def get_dashboard_data(current_user, current_permissions):
    """
    Protected route that returns dashboard data and user permissions.
    """
    print(f"Access granted to dashboard data for user: {current_user}")
    
    cpu_usage = None
    ram_usage = None
    uptime = None

    if supported_system and current_permissions.get('system_metrics', False):
        conn = get_db_connection()
        get_cpu_cmd_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'get_cpu_usage_cmd'").fetchone()
        get_ram_cmd_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'get_ram_usage_cmd'").fetchone()
        get_uptime_cmd_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'get_uptime_cmd'").fetchone()
        conn.close()

        cpu_cmd = get_cpu_cmd_row['command_value'] if get_cpu_cmd_row else sys_actions.DEFAULT_COMMANDS.get('get_cpu_usage_cmd')
        ram_cmd = get_ram_cmd_row['command_value'] if get_ram_cmd_row else sys_actions.DEFAULT_COMMANDS.get('get_ram_usage_cmd')
        uptime_cmd = get_uptime_cmd_row['command_value'] if get_uptime_cmd_row else sys_actions.DEFAULT_COMMANDS.get('get_uptime_cmd')

        if cpu_cmd and sys_actions and hasattr(sys_actions, 'execute_shell_command') and hasattr(sys_actions, 'get_cpu_usage'):
            cpu_result = sys_actions.execute_shell_command(cpu_cmd)
            if cpu_result["success"]:
                cpu_usage = sys_actions.get_cpu_usage(cpu_result["message"])
        
        if ram_cmd and sys_actions and hasattr(sys_actions, 'execute_shell_command') and hasattr(sys_actions, 'get_ram_usage'):
            ram_result = sys_actions.execute_shell_command(ram_cmd)
            if ram_result["success"]:
                ram_usage = sys_actions.get_ram_usage(ram_result["message"])

        if uptime_cmd and sys_actions and hasattr(sys_actions, 'execute_shell_command') and hasattr(sys_actions, 'get_uptime'):
            uptime_result = sys_actions.execute_shell_command(uptime_cmd)
            if uptime_result["success"]:
                uptime = sys_actions.get_uptime(uptime_result["message"])


    data = {
        'cpu_usage': cpu_usage if cpu_usage is not None else '--',
        'ram_usage': ram_usage if ram_usage is not None else '--',
        'uptime': uptime if uptime is not None else '--',
        'user': current_user,
        'permissions': current_permissions,
        'os_type': platform.system()
    }
    return jsonify({'success': True, 'data': data})

# --- New User Management Routes (Example) ---

@app.route('/api/users/register', methods=['POST'])
@token_required
def register_user(current_user, current_permissions):
    """
    Registers a new user. Accessible only by users with 'manage_users' permission.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    permissions_data = data.get('permissions', {})

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required'}), 400

    hashed_password = generate_password_hash(password)
    
    valid_permissions = {
        "shutdown": False, "restart": False, "lock": False,
        "play_pause": False, "volume": False, "system_metrics": False,
        "modify_commands": False, "manage_users": False
    }
    for perm_key, perm_value in permissions_data.items():
        if perm_key in valid_permissions and isinstance(perm_value, bool):
            valid_permissions[perm_key] = perm_value
    
    permissions_json = json.dumps(valid_permissions)

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, permissions) VALUES (?, ?, ?)",
            (username, hashed_password, permissions_json)
        )
        conn.commit()
        return jsonify({'success': True, 'message': f'User {username} registered successfully'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username already exists'}), 409
    finally:
        conn.close()

@app.route('/api/users', methods=['GET'])
@token_required
def get_users(current_user, current_permissions):
    """
    Gets the list of users. Accessible only by users with 'manage_users' permission.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, permissions FROM users").fetchall()
    conn.close()

    users_list = []
    for user in users:
        user_data = dict(user)
        user_data['permissions'] = json.loads(user_data['permissions'])
        user_data.pop('password_hash', None)
        users_list.append(user_data)
    
    return jsonify({'success': True, 'users': users_list})


@app.route('/api/users/update_permissions/<int:user_id>', methods=['PUT'])
@token_required
def update_user_permissions(current_user_username, current_permissions, user_id): # Renamed current_user to current_user_username for clarity
    """
    Updates permissions for a specific user. Accessible only by users with 'manage_users' permission.
    If the current user's permissions are updated, a new token is re-issued.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    new_permissions_data = data.get('permissions', {})

    conn = get_db_connection()
    # Fetch user_to_update's details, including their username, from DB
    user_to_update = conn.execute("SELECT id, username, permissions FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user_to_update:
        conn.close()
        return jsonify({'success': False, 'message': 'User not found'}), 404

    current_user_permissions_db = json.loads(user_to_update['permissions']) # Permissions of the user being updated

    updated_permissions = current_user_permissions_db.copy()
    for perm_key, perm_value in new_permissions_data.items():
        if perm_key in updated_permissions and isinstance(perm_value, bool):
            updated_permissions[perm_key] = perm_value
    
    permissions_json = json.dumps(updated_permissions)

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET permissions = ? WHERE id = ?",
            (permissions_json, user_id)
        )
        conn.commit()

        response = make_response(jsonify({'success': True, 'message': f'Permissions for user {user_to_update["username"]} updated successfully'}))

        # Check if the currently logged-in user is the one whose permissions were just updated
        if user_to_update['username'] == current_user_username:
            print(f"Updating token for current user: {current_user_username}")
            # Re-issue JWT token with new permissions
            new_token = jwt.encode({
                'user': current_user_username,
                'permissions': updated_permissions, # Use the newly updated permissions
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            }, app.config['SECRET_KEY'], algorithm="HS256")
            response.set_cookie('syspilot_token', new_token, httponly=True, samesite='Lax')
            response.json['message'] += " New token issued with updated permissions." # Add message for frontend

        return response # Return the response, potentially with a new cookie

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error updating permissions: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/api/users/delete/<int:user_id>', methods=['DELETE'])
@token_required
def delete_user(current_user, current_permissions, user_id):
    """
    Deletes a user. Accessible only by users with 'manage_users' permission.
    Prevents deleting the current user if they are the last administrator.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    conn = get_db_connection()
    
    user_to_delete = conn.execute("SELECT username, permissions FROM users WHERE id = ?", (user_id,)).fetchone()
    if user_to_delete:
        is_admin_to_delete = json.loads(user_to_delete['permissions']).get('manage_users', False)
        
        if is_admin_to_delete:
            admin_users = conn.execute("SELECT COUNT(*) FROM users WHERE json_extract(permissions, '$.manage_users') = 1").fetchone()[0]
            if admin_users == 1 and user_to_delete['username'] == current_user:
                conn.close()
                return jsonify({'success': False, 'message': 'Cannot delete the last administrator user.'}), 400

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        conn.commit()
        
        # If the user being deleted is the current user, log them out
        response = make_response(jsonify({'success': True, 'message': 'User deleted successfully'}))
        if user_to_delete and user_to_delete['username'] == current_user:
            response.set_cookie('syspilot_token', '', expires=0, httponly=True, samesite='Lax')
            response.json['message'] += " You have been logged out." # Indicate logout
        return response

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error deleting user: {str(e)}'}), 500
    finally:
        conn.close()


# --- Custom Commands API Routes ---

@app.route('/api/commands', methods=['GET'])
@token_required
def get_commands(current_user, current_permissions):
    """
    Retrieves custom commands from the database.
    If running on Linux, falls back to defaults from linux_actions if no custom command exists.
    Accessible only by users with 'modify_commands' permission.
    """
    if not current_permissions.get('modify_commands', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    
    if not supported_system or platform.system() != "Linux":
        return jsonify({'success': False, 'message': 'Custom command management is only available on Linux.'}), 400

    conn = get_db_connection()
    db_commands = conn.execute("SELECT command_key, command_value FROM commands").fetchall()
    conn.close()

    custom_commands = {row['command_key']: row['command_value'] for row in db_commands}
    
    final_commands = {}
    if sys_actions and hasattr(sys_actions, 'DEFAULT_COMMANDS'):
        final_commands.update(sys_actions.DEFAULT_COMMANDS)
        final_commands.update(custom_commands)
    else:
        final_commands = custom_commands

    return jsonify({'success': True, 'commands': final_commands})


@app.route('/api/commands/update', methods=['PUT'])
@token_required
def update_commands(current_user, current_permissions):
    """
    Updates custom commands in the database.
    Accessible only by users with 'modify_commands' permission.
    """
    if not current_permissions.get('modify_commands', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system or platform.system() != "Linux":
        return jsonify({'success': False, 'message': 'Custom command management is only available on Linux.'}), 400

    data = request.get_json()
    new_commands = data.get('commands', {})

    if not isinstance(new_commands, dict):
        return jsonify({'success': False, 'message': 'Invalid data format for commands.'}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for key, value in new_commands.items():
            cursor.execute(
                "INSERT OR REPLACE INTO commands (command_key, command_value) VALUES (?, ?)",
                (key, value)
            )
        conn.commit()
        return jsonify({'success': True, 'message': 'Commands updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating commands: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/api/commands/reset', methods=['POST'])
@token_required
def reset_commands(current_user, current_permissions):
    """
    Resets all custom commands to their default values (from sys_actions.DEFAULT_COMMANDS).
    Accessible only by users with 'modify_commands' permission.
    """
    if not current_permissions.get('modify_commands', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system or platform.system() != "Linux":
        return jsonify({'success': False, 'message': 'Custom command management is only available on Linux.'}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM commands")
        
        if sys_actions and hasattr(sys_actions, 'DEFAULT_COMMANDS'):
            for key, value in sys_actions.DEFAULT_COMMANDS.items():
                cursor.execute(
                    "INSERT INTO commands (command_key, command_value) VALUES (?, ?)",
                    (key, value)
                )
            conn.commit()
            return jsonify({'success': True, 'message': 'Commands reset to defaults successfully'})
        else:
            conn.rollback()
            return jsonify({'success': False, 'message': 'Default commands not found for this system type.'}), 500
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error resetting commands: {str(e)}'}), 500
    finally:
        conn.close()


# --- STATIC FILE ROUTES ---
@app.route('/css/style.css')
def serve_style_css():
    """Serves the main CSS file."""
    return send_from_directory(f'{frontend_path}/css', 'style.css')

@app.route('/js/app.js')
def serve_app_js():
    """Serves the JS file for login."""
    return send_from_directory(f'{frontend_path}/js', 'app.js')

@app.route('/js/dashboard.js')
def serve_dashboard_js():
    """Serves the JS file for the dashboard."""
    return send_from_directory(f'{frontend_path}/js', 'dashboard.js')


@app.route('/<path:filename>')
@token_required
def static_files(current_user, current_permissions, filename):
    """Serves general static files protected by authentication."""
    return send_from_directory(frontend_path, filename)

# --- API Endpoints for System Actions (MODIFIED to use custom commands) ---
@app.route('/api/action/shutdown', methods=['POST'])
@token_required
def api_shutdown(current_user, current_permissions):
    if not current_permissions.get('shutdown', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system:
        return jsonify({"success": False, "message": "System actions not available on this OS."}), 501
    
    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'shutdown_cmd'").fetchone()
    conn.close()
    
    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('shutdown_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Shutdown command not defined."}), 500

    result = sys_actions.execute_shell_command(command_to_execute)
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

@app.route('/api/action/restart', methods=['POST'])
@token_required
def api_restart(current_user, current_permissions):
    if not current_permissions.get('restart', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system:
        return jsonify({"success": False, "message": "System actions not available on this OS."}), 501

    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'restart_cmd'").fetchone()
    conn.close()
    
    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('restart_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Restart command not defined."}), 500

    result = sys_actions.execute_shell_command(command_to_execute)
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

@app.route('/api/action/lock', methods=['POST'])
@token_required
def api_lock(current_user, current_permissions):
    if not current_permissions.get('lock', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system:
        return jsonify({"success": False, "message": "System actions not available on this OS."}), 501

    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'lock_cmd'").fetchone()
    conn.close()
    
    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('lock_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Lock command not defined."}), 500

    result = sys_actions.execute_shell_command(command_to_execute)
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

@app.route('/api/action/play_pause', methods=['POST'])
@token_required
def api_play_pause(current_user, current_permissions):
    if not current_permissions.get('play_pause', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system:
        return jsonify({"success": False, "message": "System actions not available on this OS."}), 501

    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'play_pause_cmd'").fetchone()
    conn.close()
    
    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('play_pause_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Play/Pause command not defined."}), 500

    result = sys_actions.execute_shell_command(command_to_execute)
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

@app.route('/api/action/set_volume', methods=['POST'])
@token_required
def api_set_volume(current_user, current_permissions):
    if not current_permissions.get('volume', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system:
        return jsonify({"success": False, "message": "System actions not available on this OS."}), 501

    data = request.get_json()
    level = data.get('level')
    if not isinstance(level, (int, float)) or not (0 <= level <= 100):
        return jsonify({"success": False, "message": "Invalid volume level. Must be an integer or float between 0 and 100."}), 400

    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'set_volume_cmd'").fetchone()
    conn.close()
    
    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('set_volume_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Set volume command not defined."}), 500
        
    result = sys_actions.execute_shell_command(command_to_execute, level_placeholder=level)
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

@app.route('/api/volume', methods=['GET'])
@token_required
def get_current_volume(current_user, current_permissions):
    if not current_permissions.get('volume', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system or platform.system() != "Linux":
        return jsonify({"success": False, "message": "Volume retrieval not supported or implemented on this OS."}), 501

    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'get_volume_cmd'").fetchone()
    conn.close()

    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('get_volume_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Get volume command not defined."}), 500

    shell_result = sys_actions.execute_shell_command(command_to_execute)
    
    if shell_result["success"]:
        volume_level_result = sys_actions.get_volume(shell_result["message"])
        if volume_level_result["success"]:
            return jsonify({'success': True, 'level': volume_level_result['level']}), 200
        else:
            return jsonify({'success': False, 'message': volume_level_result['message'] or 'Failed to parse volume output.'}), 500
    else:
        return jsonify({'success': False, 'message': shell_result['message'] or 'Failed to execute get volume command.'}), 500


if __name__ == '__main__':
    if supported_system:
        if app.config['SECRET_KEY'] and default_admin_username and default_admin_password:
            app.run(host='0.0.0.0', port=5000, debug=True)
        else:
            print("Please make sure to configure the .env or settings.ini file correctly.")
            print("Make sure the following variables are set: SECRET_KEY, DEFAULT_USERNAME, DEFAULT_PASSWORD, DATABASE_FILENAME (optional)")
    else:
        print("Backend server cannot run: Unsupported operating system. Please use Linux or Windows.")


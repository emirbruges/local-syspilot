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
else:
    print("System not supported, please use Linux.")

load_dotenv()

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
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
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
            # MODIFICACIÓN: Añadir nuevas permisos por defecto
            default_permissions = {
                "shutdown": True, "restart": True, "lock": True,
                "play_pause": True, "media_next": True, "media_previous": True,
                "volume": True, "volume_mute": True, "system_metrics": True,
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
        
        # MODIFICACIÓN CLAVE: Eliminar todos los comandos existentes y volver a insertar los valores predeterminados
        if supported_system and sys_actions and hasattr(sys_actions, 'DEFAULT_COMMANDS'):
            print("Resetting and ensuring all default commands are present in the database...")
            try:
                cursor.execute("DELETE FROM commands") # Eliminar todos los comandos existentes
                for key, value in sys_actions.DEFAULT_COMMANDS.items():
                    cursor.execute(
                        "INSERT INTO commands (command_key, command_value) VALUES (?, ?)",
                        (key, value)
                    )
                conn.commit()
                print("Default commands reset and populated successfully.")
            except Exception as e:
                conn.rollback() # Rollback en caso de error
                print(f"Error resetting or populating default commands: {e}")
        else:
            print("Cannot populate default commands: sys_actions.DEFAULT_COMMANDS not found or system not supported.")
        conn.close()

# Ensure the database is initialized when the application starts
with app.app_context():
    init_db()

def force_relogin_response():
    if request.accept_mimetypes.accept_html or not request.path.startswith('/api/'):
        response = redirect(url_for('index'))
        response.set_cookie('syspilot_token', '', expires=0, httponly=True, samesite='Lax')
        return response
    else:
        response = make_response(jsonify({
            'success': False,
            'message': 'Your session has expired or is invalid. You need to log in again.'
            }), 401)
        response.set_cookie('syspilot_token', '', expires=0, httponly=True, samesite='Lax')
        return response

def token_required(f):
    """
    Decorator to protect routes, verifying the JWT token in cookies.
    Also checks token permissions against the database on each request.
    If permissions are inconsistent, a new token is issued and a message is returned.
    If the token is invalid/expired or user not found, it forces a re-login.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('syspilot_token')

        if not token:
            print("Token no encontrado en cookies.")
            return force_relogin_response() # No hay token, forzar login

        try:
            # Decodificar el token para obtener el usuario y los permisos incrustados
            token_data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            username_from_token = token_data['user']
            permissions_from_token = token_data.get('permissions', {})

            # Obtener los últimos permisos del usuario de la base de datos
            conn = get_db_connection()
            db_user_row = conn.execute("SELECT permissions FROM users WHERE username = ?", (username_from_token,)).fetchone()
            conn.close()

            # Si el usuario no se encuentra en la base de datos, el token es inválido (aunque decodifique)
            if not db_user_row:
                print(f"User '{username_from_token}' not found in DB. Forcing re-login.")
                return force_relogin_response()
            
            db_permissions = json.loads(db_user_row['permissions'])

            # Comparar permisos: convertir a lista ordenada de pares (clave, valor) para comparación fiable
            sorted_token_perms = sorted(permissions_from_token.items())
            sorted_db_perms = sorted(db_permissions.items())

            # Si los permisos son inconsistentes (cambiaron en la DB)
            if sorted_token_perms != sorted_db_perms:
                print(f"Permissions for user '{username_from_token}' inconsistent with DB. Issuing new token.")
                
                # Emitir un nuevo token con los permisos actualizados de la DB
                new_token = jwt.encode({
                    'user': username_from_token,
                    'permissions': db_permissions, # Usa los permisos actualizados de la DB
                    'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
                }, app.config['SECRET_KEY'], algorithm="HS256")

                # Crear una respuesta que establezca la nueva cookie y contenga un mensaje para el frontend
                response_on_permission_change = make_response(jsonify({
                    'success': True, # Esto es crucial para que el frontend no trate como error 401
                    'message': 'Your permissions have changed. The system has updated your session. Please review your controls.',
                    'permission_change': True # Flag para que el frontend sepa que hubo un cambio de permisos
                }), 200) # Retornar 200 OK para que el frontend procese el mensaje
                response_on_permission_change.set_cookie('syspilot_token', new_token, httponly=True, samesite='Lax')
                
                # La función decorada no se ejecuta, el controlador de ruta que la llamó debe manejar esto
                return response_on_permission_change
            
            # Si todas las comprobaciones pasan, pasar los ÚLTIMOS permisos de la DB a la función
            return f(username_from_token, db_permissions, *args, **kwargs)

        except jwt.ExpiredSignatureError:
            print("Token expired. Forcing re-login.")
            return force_relogin_response()
        except jwt.InvalidTokenError:
            print("Invalid token. Forcing re-login.")
            return force_relogin_response()
        except Exception as e:
            # Capturar cualquier otro error inesperado durante la validación del token o la búsqueda en la DB
            print(f"An unexpected error occurred during token validation: {str(e)}")
            return force_relogin_response() # Denegar acceso por errores inesperados
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
            cpu_result = sys_actions.execute_shell_command(cpu_cmd, 'get_cpu_usage_cmd')
            if cpu_result["success"]:
                cpu_usage = sys_actions.get_cpu_usage(cpu_result["message"])
        
        if ram_cmd and sys_actions and hasattr(sys_actions, 'execute_shell_command') and hasattr(sys_actions, 'get_ram_usage'):
            ram_result = sys_actions.execute_shell_command(ram_cmd, 'get_ram_usage_cmd')
            if ram_result["success"]:
                ram_usage = sys_actions.get_ram_usage(ram_result["message"])

        if uptime_cmd and sys_actions and hasattr(sys_actions, 'execute_shell_command') and hasattr(sys_actions, 'get_uptime'):
            uptime_result = sys_actions.execute_shell_command(uptime_cmd, 'get_uptime_cmd')
            if uptime_result["success"]:
                uptime = sys_actions.get_uptime(uptime_result["message"])


    data = {
        'cpu_usage': cpu_usage if cpu_usage is not None else '--',
        'ram_usage': ram_usage if ram_usage is not None else '--',
        'uptime': uptime if uptime is not None else '--',
        'user': current_user,
        'permissions': current_permissions, # This will be the fresh DB permissions
        'os_type': platform.system()
    }
    # For HTML routes, if the token was updated, the redirect handles the new cookie.
    # For API routes, the token_required decorator handles setting the new cookie directly
    # and then the current_permissions passed to `get_dashboard_data` will be the correct ones.
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
        "play_pause": False, "media_next": False, "media_previous": False,
        "volume": False, "volume_mute": False, "system_metrics": False,
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

    result = sys_actions.execute_shell_command(command_to_execute, 'shutdown_cmd')
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

    result = sys_actions.execute_shell_command(command_to_execute, 'restart_cmd')
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

    result = sys_actions.execute_shell_command(command_to_execute, 'lock_cmd')
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

    result = sys_actions.execute_shell_command(command_to_execute, 'play_pause_cmd')
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

# NUEVO ENDPOINT: Media Next
@app.route('/api/action/media_next', methods=['POST'])
@token_required
def api_media_next(current_user, current_permissions):
    if not current_permissions.get('media_next', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system:
        return jsonify({"success": False, "message": "System actions not available on this OS."}), 501

    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'media_next_cmd'").fetchone()
    conn.close()
    
    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('media_next_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Media Next command not defined."}), 500

    result = sys_actions.execute_shell_command(command_to_execute, 'media_next_cmd')
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

# NUEVO ENDPOINT: Media Previous
@app.route('/api/action/media_previous', methods=['POST'])
@token_required
def api_media_previous(current_user, current_permissions):
    if not current_permissions.get('media_previous', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system:
        return jsonify({"success": False, "message": "System actions not available on this OS."}), 501

    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'media_previous_cmd'").fetchone()
    conn.close()
    
    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('media_previous_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Media Previous command not defined."}), 500

    result = sys_actions.execute_shell_command(command_to_execute, 'media_previous_cmd')
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
        
    result = sys_actions.execute_shell_command(command_to_execute, 'set_volume_cmd', level_placeholder=level)
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

# NUEVO ENDPOINT: Volume Mute/Unmute
@app.route('/api/action/volume_mute', methods=['POST'])
@token_required
def api_volume_mute(current_user, current_permissions):
    if not current_permissions.get('volume_mute', False): # Use volume_mute permission
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    if not supported_system:
        return jsonify({"success": False, "message": "System actions not available on this OS."}), 501

    conn = get_db_connection()
    command_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'volume_mute_cmd'").fetchone()
    conn.close()
    
    command_to_execute = command_row['command_value'] if command_row else sys_actions.DEFAULT_COMMANDS.get('volume_mute_cmd')

    if not command_to_execute:
        return jsonify({"success": False, "message": "Volume Mute command not defined."}), 500

    result = sys_actions.execute_shell_command(command_to_execute, 'volume_mute_cmd')
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

@app.route('/api/volume', methods=['GET'])
@token_required
def get_current_volume(current_user, current_permissions):
    # MODIFICACIÓN: Ahora devuelve nivel Y estado de mute
    if not current_permissions.get('volume', False) and not current_permissions.get('volume_mute', False):
        return jsonify({'success': False, 'message': 'Permission denied for volume or mute status.'}), 403

    if not supported_system or platform.system() != "Linux":
        return jsonify({"success": False, "message": "Volume retrieval not supported or implemented on this OS."}), 501

    conn = get_db_connection()
    get_volume_cmd_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'get_volume_cmd'").fetchone()
    get_mute_status_cmd_row = conn.execute("SELECT command_value FROM commands WHERE command_key = 'get_mute_status_cmd'").fetchone()
    conn.close()

    command_to_execute_volume = get_volume_cmd_row['command_value'] if get_volume_cmd_row else sys_actions.DEFAULT_COMMANDS.get('get_volume_cmd')
    command_to_execute_mute = get_mute_status_cmd_row['command_value'] if get_mute_status_cmd_row else sys_actions.DEFAULT_COMMANDS.get('get_mute_status_cmd')

    volume_level = None
    is_muted_status = None

    # Get volume level
    if command_to_execute_volume and sys_actions and hasattr(sys_actions, 'get_volume'):
        shell_result_volume = sys_actions.execute_shell_command(command_to_execute_volume, 'get_volume_cmd')
        if shell_result_volume["success"]:
            volume_level_result = sys_actions.get_volume(shell_result_volume["message"])
            if volume_level_result["success"]:
                volume_level = volume_level_result['level']
            else:
                print(f"Warning: Failed to parse volume level: {volume_level_result['message']}")
        else:
            print(f"Warning: Failed to execute get_volume_cmd: {shell_result_volume['message']}")

    # Get mute status
    if command_to_execute_mute and sys_actions and hasattr(sys_actions, 'is_muted'):
        shell_result_mute = sys_actions.execute_shell_command(command_to_execute_mute, 'get_mute_status_cmd')
        if shell_result_mute["success"]:
            mute_status_result = sys_actions.is_muted(shell_result_mute["message"])
            if mute_status_result["success"]:
                is_muted_status = mute_status_result['is_muted']
            else:
                print(f"Warning: Failed to parse mute status: {mute_status_result['message']}")
        else:
            print(f"Warning: Failed to execute get_mute_status_cmd: {shell_result_mute['message']}")

    # Return combined result
    if volume_level is not None or is_muted_status is not None:
        return jsonify({'success': True, 'level': volume_level, 'is_muted': is_muted_status}), 200
    else:
        return jsonify({'success': False, 'message': 'Failed to retrieve volume or mute status.'}), 500


if __name__ == '__main__':
    if supported_system:
        if app.config['SECRET_KEY'] and default_admin_username and default_admin_password:
            app.run(host='0.0.0.0', port=5000, debug=True)
        else:
            print("Please make sure to configure the .env or settings.ini file correctly.")
            print("Make sure the following variables are set: SECRET_KEY, DEFAULT_USERNAME, DEFAULT_PASSWORD, DATABASE_FILENAME (optional)")
    else:
        print("Backend server cannot run: Unsupported operating system. Please use Linux.")

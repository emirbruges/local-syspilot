from dotenv import load_dotenv
import os
import sqlite3
from flask import Flask, request, jsonify, make_response, render_template, send_from_directory, redirect, url_for
from flask_cors import CORS
import jwt
import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

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

# Get default admin credentials from environment variables
default_admin_username = os.getenv("DEFAULT_USERNAME")
default_admin_password = os.getenv("DEFAULT_PASSWORD")
database_filename = os.getenv("DATABASE_FILENAME", 'syspilot.db') # Default to 'syspilot.db' if not specified

# --- DATABASE CONFIGURATION ---
DATABASE = os.path.join(os.path.dirname(__file__), database_filename) # Use the database_filename variable

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # Allows accessing rows as dictionaries
    return conn

def init_db():
    """Initializes the database and creates the users table if it doesn't exist."""
    with app.app_context(): # Required to use app.config and other application variables
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                permissions TEXT NOT NULL -- Stores permissions as a JSON string (e.g., '{"shutdown": true, "restart": false}')
            )
        ''')
        conn.commit()

        # Optional: Create a default admin user if none exists (for the first run)
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            print("No users found. Creating default administrator user...")

            # Check if default admin credentials are provided, otherwise use fallback
            username_to_create = default_admin_username if default_admin_username else "admin"
            password_to_create = default_admin_password if default_admin_password else "admin123" # CHANGE IN PRODUCTION!

            hashed_password = generate_password_hash(password_to_create)
            # Default permissions for the administrator (all true for now)
            default_permissions = {
                "shutdown": True,
                "restart": True,
                "lock": True,
                "play_pause": True,
                "volume": True,
                "system_metrics": True,
                "modify_commands": True,
                "manage_users": True
            }
            import json
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
            current_permissions = data.get('permissions', {}) # Get permissions from the token
            return f(current_user, current_permissions, *args, **kwargs) # Pass permissions to the decorator
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
            # Attempt to decode to see if the token is valid, otherwise ignore it
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            return redirect(url_for('dashboard'))
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass # If the token is invalid/expired, simply show the login

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
def dashboard(current_user, current_permissions): # Receive permissions
    """Renders the dashboard if the user is authenticated."""
    # Permissions are not directly used here for rendering, but can be used in JS
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
        import json
        permissions = json.loads(user['permissions']) # Load permissions as a dictionary

        token = jwt.encode({
            'user': username,
            'permissions': permissions, # Include permissions in the token
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
    
    # Real logic to get system metrics would go here
    # For now, we use example data:
    data = {
        'cpu_usage': 25,
        'ram_usage': 60,
        'uptime': '18h 45m',
        'user': current_user,
        'permissions': current_permissions # Send permissions to the frontend
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
    
    # Validate that the submitted permissions are boolean type for each expected key
    valid_permissions = {
        "shutdown": False, "restart": False, "lock": False,
        "play_pause": False, "volume": False, "system_metrics": False,
        "modify_commands": False, "manage_users": False
    }
    for perm_key, perm_value in permissions_data.items():
        if perm_key in valid_permissions and isinstance(perm_value, bool):
            valid_permissions[perm_key] = perm_value
    
    import json
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
    import json
    for user in users:
        user_data = dict(user) # Convert SQLite row to a dictionary
        user_data['permissions'] = json.loads(user_data['permissions']) # Deserialize permissions
        # Do not include password_hash
        user_data.pop('password_hash', None)
        users_list.append(user_data)
    
    return jsonify({'success': True, 'users': users_list})


@app.route('/api/users/update_permissions/<int:user_id>', methods=['PUT'])
@token_required
def update_user_permissions(current_user, current_permissions, user_id):
    """
    Updates permissions for a specific user. Accessible only by users with 'manage_users' permission.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    new_permissions_data = data.get('permissions', {})

    conn = get_db_connection()
    user = conn.execute("SELECT permissions FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        conn.close()
        return jsonify({'success': False, 'message': 'User not found'}), 404

    import json
    current_user_permissions = json.loads(user['permissions'])

    # Merge new permissions with existing ones, validating types
    updated_permissions = current_user_permissions.copy()
    for perm_key, perm_value in new_permissions_data.items():
        if perm_key in updated_permissions and isinstance(perm_value, bool):
            updated_permissions[perm_key] = perm_value
    
    permissions_json = json.dumps(updated_permissions)

    try:
        conn.execute(
            "UPDATE users SET permissions = ? WHERE id = ?",
            (permissions_json, user_id)
        )
        conn.commit()
        return jsonify({'success': True, 'message': f'Permissions for user {user_id} updated successfully'})
    except Exception as e:
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
    
    # Prevent the last administrator user from deleting themselves
    user_to_delete = conn.execute("SELECT username, permissions FROM users WHERE id = ?", (user_id,)).fetchone()
    if user_to_delete:
        import json
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
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error deleting user: {str(e)}'}), 500
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
def static_files(current_user, current_permissions, filename): # Permissions are also passed here
    """Serves general static files protected by authentication."""
    # Permissions are not necessarily used here, but the decorator passes them
    return send_from_directory(frontend_path, filename)

if __name__ == '__main__':
    if app.config['SECRET_KEY'] and default_admin_username and default_admin_password:
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        print("Please make sure to configure the .env or settings.ini file correctly.")
        print("Make sure the following variables are set: SECRET_KEY, DEFAULT_USERNAME, DEFAULT_PASSWORD, DATABASE_FILENAME (optional)")

from dotenv import load_dotenv
import os
import sqlite3
from flask import Flask, request, jsonify, make_response, render_template, send_from_directory, redirect, url_for
from flask_cors import CORS
import jwt
import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash # Importamos para manejo de contraseñas

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
default_admin_password = os.getenv("DEFAULT_PASSWORD") # ¡CAMBIAR EN PRODUCCIÓN!
database_filename = os.getenv("DATABASE_FILENAME", 'syspilot.db')


# --- DATABASE CONFIGURATION ---
DATABASE = os.path.join(os.path.dirname(__file__), 'syspilot.db')

def get_db_connection():
    """Establece una conexión con la base de datos SQLite."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # Permite acceder a las filas como diccionarios
    return conn

def init_db():
    """Inicializa la base de datos y crea la tabla de usuarios si no existe."""
    with app.app_context(): # Necesario para usar app.config y otras variables de la aplicación
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                permissions TEXT NOT NULL -- Almacenará los permisos como una cadena JSON (ej: '{"shutdown": true, "restart": false}')
            )
        ''')
        conn.commit()

        # Opcional: Crear un usuario administrador si no existe ninguno (para la primera ejecución)
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            print("No se encontraron usuarios. Creando usuario administrador por defecto...")

            hashed_password = generate_password_hash(default_admin_password)
            # Permisos por defecto para el administrador (todos en true por ahora)
            default_permissions = {
                "shutdown": True,
                "restart": True,
                "lock": True,
                "play_pause": True,
                "volume": True,
                "system_metrics": True,
                "modify_commands": True,
                "manage_users": True # Nuevo permiso para gestionar usuarios
            }
            import json
            permissions_json = json.dumps(default_permissions)

            try:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, permissions) VALUES (?, ?, ?)",
                    (default_admin_username, hashed_password, permissions_json)
                )
                conn.commit()
                print(f"Usuario administrador '{default_admin_username}' creado con contraseña por defecto.")
            except sqlite3.IntegrityError:
                print(f"El usuario '{default_admin_username}' ya existe.")
        conn.close()

# Asegurarse de que la base de datos se inicialice al inicio de la aplicación
with app.app_context():
    init_db()


def token_required(f):
    """
    Decorador para proteger rutas, verificando el token JWT en las cookies.
    Redirige al login si el token es inválido o no existe.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('syspilot_token')
        if not token:
            print("Token no encontrado en cookies. Redirigiendo a /")
            return redirect('/')
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['user']
            current_permissions = data.get('permissions', {}) # Obtener permisos del token
            return f(current_user, current_permissions, *args, **kwargs) # Pasar permisos al decorador
        except jwt.ExpiredSignatureError:
            print("Token expirado. Redirigiendo a /")
            return redirect('/')
        except jwt.InvalidTokenError:
            print("Token inválido. Redirigiendo a /")
            return redirect('/')
    return decorated

# --- RUTAS HTML ---
@app.route('/')
def index():
    token = request.cookies.get('syspilot_token')
    if token:
        try:
            # Intentar decodificar para ver si el token es válido, si no, lo ignoramos
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            return redirect(url_for('dashboard'))
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass # Si el token es inválido/expirado, simplemente mostramos el login

    return render_template('index.html')

@app.route('/index.html')
@app.route('/dashboard.html')
def redirect_to_root_or_dashboard():
    """Redirige las solicitudes directas a index.html o dashboard.html."""
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
def dashboard(current_user, current_permissions): # Recibimos los permisos
    """Renderiza el dashboard si el usuario está autenticado."""
    # Los permisos no se usan directamente aquí para renderizar, pero se pueden usar en el JS
    return render_template('dashboard.html')

# --- RUTAS DE LA API ---
@app.route('/api/login', methods=['POST'])
def login():
    """Maneja el inicio de sesión del usuario."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        import json
        permissions = json.loads(user['permissions']) # Cargar permisos como diccionario

        token = jwt.encode({
            'user': username,
            'permissions': permissions, # Incluir permisos en el token
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, app.config['SECRET_KEY'], algorithm="HS256")

        response = make_response(jsonify({'success': True, 'message': 'Inicio de sesión exitoso'}))
        response.set_cookie('syspilot_token', token, httponly=True, samesite='Lax')
        return response
    
    return jsonify({'success': False, 'message': 'Credenciales incorrectas'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """Cierra la sesión del usuario eliminando la cookie."""
    response = make_response(jsonify({'success': True, 'message': 'Sesión cerrada'}))
    response.set_cookie('syspilot_token', '', expires=0, httponly=True, samesite='Lax')
    return response

@app.route('/api/dashboard-data')
@token_required
def get_dashboard_data(current_user, current_permissions):
    """
    Ruta protegida que devuelve datos del dashboard y los permisos del usuario.
    """
    print(f"Acceso concedido a la data del dashboard para el usuario: {current_user}")
    
    # Aquí iría la lógica real para obtener métricas del sistema
    # Por ahora, usamos datos de ejemplo:
    data = {
        'cpu_usage': 25,
        'ram_usage': 60,
        'uptime': '18h 45m',
        'user': current_user,
        'permissions': current_permissions # Enviar permisos al frontend
    }
    return jsonify({'success': True, 'data': data})

# --- Nuevas Rutas de Gestión de Usuarios (Ejemplo) ---

@app.route('/api/users/register', methods=['POST'])
@token_required
def register_user(current_user, current_permissions):
    """
    Registra un nuevo usuario. Solo accesible por usuarios con permiso 'manage_users'.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permiso denegado'}), 403

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    permissions_data = data.get('permissions', {})

    if not username or not password:
        return jsonify({'success': False, 'message': 'Se requiere nombre de usuario y contraseña'}), 400

    hashed_password = generate_password_hash(password)
    
    # Validar que los permisos enviados sean de tipo booleano para cada clave esperada
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
        return jsonify({'success': True, 'message': f'Usuario {username} registrado exitosamente'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'El nombre de usuario ya existe'}), 409
    finally:
        conn.close()

@app.route('/api/users', methods=['GET'])
@token_required
def get_users(current_user, current_permissions):
    """
    Obtiene la lista de usuarios. Solo accesible por usuarios con permiso 'manage_users'.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permiso denegado'}), 403
    
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, permissions FROM users").fetchall()
    conn.close()

    users_list = []
    import json
    for user in users:
        user_data = dict(user) # Convierte la fila SQLite en un diccionario
        user_data['permissions'] = json.loads(user_data['permissions']) # Deserializa los permisos
        # No incluir password_hash
        del user_data['password_hash']
        users_list.append(user_data)
    
    return jsonify({'success': True, 'users': users_list})


@app.route('/api/users/update_permissions/<int:user_id>', methods=['PUT'])
@token_required
def update_user_permissions(current_user, current_permissions, user_id):
    """
    Actualiza los permisos de un usuario específico. Solo accesible por usuarios con permiso 'manage_users'.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permiso denegado'}), 403

    data = request.get_json()
    new_permissions_data = data.get('permissions', {})

    conn = get_db_connection()
    user = conn.execute("SELECT permissions FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        conn.close()
        return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404

    import json
    current_user_permissions = json.loads(user['permissions'])

    # Fusionar los permisos nuevos con los existentes, validando los tipos
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
        return jsonify({'success': True, 'message': f'Permisos del usuario {user_id} actualizados exitosamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al actualizar permisos: {str(e)}'}), 500
    finally:
        conn.close()


@app.route('/api/users/delete/<int:user_id>', methods=['DELETE'])
@token_required
def delete_user(current_user, current_permissions, user_id):
    """
    Elimina un usuario. Solo accesible por usuarios con permiso 'manage_users'.
    No se permite eliminar al propio usuario si es el último administrador.
    """
    if not current_permissions.get('manage_users', False):
        return jsonify({'success': False, 'message': 'Permiso denegado'}), 403

    conn = get_db_connection()
    
    # Evitar que el último usuario administrador se elimine a sí mismo
    user_to_delete = conn.execute("SELECT username, permissions FROM users WHERE id = ?", (user_id,)).fetchone()
    if user_to_delete:
        import json
        is_admin_to_delete = json.loads(user_to_delete['permissions']).get('manage_users', False)
        
        if is_admin_to_delete:
            admin_users = conn.execute("SELECT COUNT(*) FROM users WHERE json_extract(permissions, '$.manage_users') = 1").fetchone()[0]
            if admin_users == 1 and user_to_delete['username'] == current_user:
                conn.close()
                return jsonify({'success': False, 'message': 'No puedes eliminar al último usuario administrador.'}), 400

    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'message': 'Usuario no encontrado'}), 404
        conn.commit()
        return jsonify({'success': True, 'message': 'Usuario eliminado exitosamente'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error al eliminar usuario: {str(e)}'}), 500
    finally:
        conn.close()


# --- RUTAS DE ARCHIVOS ESTATICOS ---
@app.route('/css/style.css')
def serve_style_css():
    """Sirve el archivo CSS principal."""
    return send_from_directory(f'{frontend_path}/css', 'style.css')

@app.route('/js/app.js')
def serve_app_js():
    """Sirve el archivo JS para el login."""
    return send_from_directory(f'{frontend_path}/js', 'app.js')

@app.route('/js/dashboard.js')
def serve_dashboard_js():
    """Sirve el archivo JS para el dashboard."""
    return send_from_directory(f'{frontend_path}/js', 'dashboard.js')


@app.route('/<path:filename>')
@token_required
def static_files(current_user, current_permissions, filename): # También se pasan permisos aquí
    """Sirve archivos estáticos generales protegidos por autenticación."""
    # No es necesario usar los permisos aquí, pero el decorador los pasa
    return send_from_directory(frontend_path, filename)

if __name__ == '__main__':
    if app.config['SECRET_KEY'] and default_admin_username and default_admin_password:
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        print("Please make sure to configure the .env or settings.ini file correctly.")
        print("""Make sure the following variables inside of it: SECRET_KEY, DEFAULT_USERNAME, DEFAULT_PASSWORD, DATABASE_FILENAME(optional)""")

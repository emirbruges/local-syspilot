from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import datetime
from functools import wraps

# --- CONFIGURACIÓN DE LA APP ---
app = Flask(__name__)
CORS(app)  # Permite peticiones desde el frontend

# IMPORTANTE: Esta clave debe ser secreta, compleja y nunca exponerse.
# En un entorno de producción, cárgala desde una variable de entorno.
app.config['SECRET_KEY'] = 'clave-super-secreta-para-local-syspilot-2025'

# Credenciales de ejemplo (reemplazar en el futuro por un sistema de usuarios)
VALID_USERNAME = "admin"
VALID_PASSWORD = "password123"


# --- DECORADOR DE AUTENTICACIÓN ---
def token_required(f):
    """
    Un decorador para verificar que un token JWT válido está presente en la cabecera.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({'success': False, 'message': 'Falta el token de autenticación'}), 401

        try:
            # Decodificar el token usando la clave secreta
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['user']
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'El token ha expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'El token no es válido'}), 401
        
        # Pasa el nombre del usuario a la función de la ruta
        return f(current_user, *args, **kwargs)
    return decorated


# --- RUTAS DE LA API ---
@app.route('/api/login', methods=['POST'])
def login():
    """
    Gestiona el inicio de sesión y devuelve un token JWT si las credenciales son válidas.
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'success': False, 'message': 'Faltan credenciales'}), 400

    username = data.get('username')
    password = data.get('password')

    if username == VALID_USERNAME and password == VALID_PASSWORD:
        # Genera el token con una validez de 1 hora
        token = jwt.encode({
            'user': username,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        
        return jsonify({'success': True, 'token': token})
    
    return jsonify({'success': False, 'message': 'Credenciales incorrectas'}), 401


@app.route('/api/dashboard-data')
@token_required  # Proteger esta ruta con el decorador
def get_dashboard_data(current_user):
    """
    Ruta protegida que solo devuelve datos si el token es válido.
    """
    # El argumento 'current_user' lo provee el decorador
    print(f"Acceso concedido a la data del dashboard para el usuario: {current_user}")
    
    # Aquí iría la lógica real para obtener métricas del sistema
    # Por ahora, usamos datos de ejemplo:
    data = {
        'cpu_usage': 25,
        'ram_usage': 60,
        'uptime': '18h 45m',
        'user': current_user
    }
    return jsonify({'success': True, 'data': data})


# --- INICIO DE LA APP ---
if __name__ == '__main__':
    # Escucha en 0.0.0.0 para ser accesible desde otros dispositivos en la red local
    app.run(host='0.0.0.0', port=5000, debug=True)

# backend/system_actions/linux_actions.py
import subprocess
import os
import re # Importar para expresiones regulares

# Define los comandos por defecto para Linux
# Estos son los valores que se usarán si no hay comandos personalizados en la DB
DEFAULT_COMMANDS = {
    "shutdown_cmd": "sudo systemctl poweroff",
    "restart_cmd": "sudo systemctl reboot",
    "lock_cmd": "gnome-screensaver-command -l || loginctl lock-session",
    "play_pause_cmd": "playerctl play-pause",
    "media_next_cmd": "playerctl next",
    "media_previous_cmd": "playerctl previous",
    "set_volume_cmd": "pactl set-sink-volume @DEFAULT_SINK@ {}%",
"get_volume_cmd": "pactl get-sink-volume @DEFAULT_SINK@ || amixer get Master",
    "volume_mute_cmd": "pactl set-sink-mute @DEFAULT_SINK@ toggle || amixer -D pulse sset Master toggle",
    "get_cpu_usage_cmd": "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage}'",
    "get_ram_usage_cmd": "free -m | awk 'NR==2{printf \"%.0f\", $3*100/$2 }'",
    "get_uptime_cmd": "uptime -p | sed 's/^up //'",
    "get_mute_status_cmd": "pactl get-sink-mute @DEFAULT_SINK@ || amixer get Master"
}

SUCCESS_COMMANDS_MESSAGES = {
    "shutdown_cmd": "Shutdown command executed successfully.",
    "restart_cmd": "Restart command executed successfully.",
    "lock_cmd": "Lock session command executed successfully.",
    "play_pause_cmd": "Play/Pause command executed successfully.",
    "media_next_cmd": "Media next command executed successfully.",
    "media_previous_cmd": "Media previous command executed successfully.",
    "set_volume_cmd": "Set volume command executed successfully.",
    "get_volume_cmd": "Get volume command executed successfully.",
    "volume_mute_cmd": "Mute command executed successfully.",
    "get_cpu_usage_cmd": "Get CPU usage command executed successfully.",
    "get_ram_usage_cmd": "Get RAM usage command executed successfully.",
    "get_uptime_cmd": "Get uptime command executed successfully.",
    "get_mute_status_cmd": "Get mute status command executed successfully."
}

def execute_shell_command(command_string, command_action, level_placeholder=None):
    """
    Ejecuta un comando de shell.
    Si level_placeholder es un valor, reemplaza el placeholder en el comando.
    """
    if level_placeholder is not None and "{}" in command_string:
        command_string = command_string.format(level_placeholder)
    
    try:
        # Se usa shell=True para permitir comandos con pipes (||) como en lock_cmd o set_volume_cmd
        result = subprocess.run(command_string, shell=True, check=True, capture_output=True, text=True)
        print(f"Command executed: '{command_string}'")
        stdout_message = result.stdout.strip()
        print(f"Stdout: {stdout_message}")
        if result.stderr:
            print(f"Stderr: {result.stderr.strip()}")
        
        final_message = stdout_message if stdout_message else SUCCESS_COMMANDS_MESSAGES[command_action]
        
        return {"success": True, "message": final_message}
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.strip() or f"Command '{command_string}' failed with exit code {e.returncode}."
        print(f"Error executing command: {error_message}")
        return {"success": False, "message": error_message}
    except FileNotFoundError:
        return {"success": False, "message": f"Command not found for: '{command_string.split(' ')[0]}'."}
    except Exception as e:
        return {"success": False, "message": f"An unexpected error occurred: {str(e)}"}

# Las funciones de acción específicas ahora simplemente tienen un 'pass'
# app.py las obtendrá de la DB o DEFAULT_COMMANDS y ejecutará directamente
def shutdown():
    pass

def restart():
    pass

def lock_session():
    pass

def play_pause_media():
    pass

def media_next():
    pass

def media_previous():
    pass

def volume_mute():
    pass

def set_volume(level):
    pass

def get_cpu_usage(command_output):
    """
    Parsea la salida del comando para obtener el uso de CPU.
    """
    if command_output and command_output.strip():
        try:
            return float(command_output.strip())
        except ValueError:
            print(f"Warning: Could not parse CPU usage '{command_output}' to float.")
            return None
    return None

def get_ram_usage(command_output): # MODIFIED: Accepts command_output
    """
    Parsea la salida del comando para obtener el uso de RAM.
    """
    if command_output and command_output.strip():
        try:
            return float(command_output.strip())
        except ValueError:
            print(f"Warning: Could not parse RAM usage '{command_output}' to float.")
            return None
    return None

def get_uptime(command_output): # MODIFIED: Accepts command_output
    """
    Retorna la salida del comando de uptime directamente.
    """
    return command_output.strip() if command_output else None

def get_volume_level_from_output(output):
    """
    Parsea la salida de un comando de volumen para extraer el nivel de porcentaje.
    Intenta parsear la salida de pactl o amixer.
    """
    if not output:
        return None

    # Intenta parsear salida de pactl: Volume: 0: 65536 / 100% / 0.00 dB
    match_pactl = re.search(r'(\d+)%', output)
    if match_pactl:
        return int(match_pactl.group(1))

    # Intenta parsear salida de amixer: [75%]
    match_amixer = re.search(r'\[(\d+)%\]', output)
    if match_amixer:
        return int(match_amixer.group(1))
    
    print(f"Warning: Could not parse volume level from output: '{output}'")
    return None # No se pudo extraer el porcentaje

def get_volume(command_output):
    """
    Esta función ahora recibe la salida de un comando de volumen y la parsea.
    """
    level = get_volume_level_from_output(command_output)
    if level is not None:
        return {"success": True, "level": level}
    else:
        return {"success": False, "message": "Failed to parse volume level from command output."}

def is_muted(command_output):
    """
    Parsea la salida de un comando de mute para determinar si el volumen está muteado.
    Busca patrones de 'Mute: yes' o '[off]' para pactl/amixer.
    """
    if not command_output:
        return {"success": False, "is_muted": None, "message": "No output to parse mute status."}

    # pactl output example: "Mute: yes" or "Mute: no"
    # amixer output example: "[off]" or "[on]"
    is_muted_val = False
    if re.search(r'Mute: yes', command_output, re.IGNORECASE) or re.search(r'\[off\]', command_output, re.IGNORECASE):
        is_muted_val = True
    elif re.search(r'Mute: no', command_output, re.IGNORECASE) or re.search(r'\[on\]', command_output, re.IGNORECASE):
        is_muted_val = False
    else:
        print(f"Warning: Could not parse mute status from output: '{command_output}'")
        return {"success": False, "is_muted": None, "message": "Could not parse mute status."}
    
    return {"success": True, "is_muted": is_muted_val}

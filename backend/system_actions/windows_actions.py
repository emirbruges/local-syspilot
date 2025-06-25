# backend/system_actions/windows_actions.py

# Define comandos por defecto para Windows (placeholders)
DEFAULT_COMMANDS = {
    "shutdown_cmd": "shutdown /s /t 0",
    "restart_cmd": "shutdown /r /t 0",
    "lock_cmd": "Rundll32.exe user32.dll,LockWorkStation",
    "play_pause_cmd": "Not implemented for Windows yet.", # Puede requerir COM objects o Powershell
    "set_volume_cmd": "Not implemented for Windows yet.", # Puede requerir COM objects o Powershell
    "get_cpu_usage_cmd": "Not implemented for Windows yet.",
    "get_ram_usage_cmd": "Not implemented for Windows yet.",
    "get_uptime_cmd": "Not implemented for Windows yet."
}

def execute_shell_command(command_string, level_placeholder=None):
    """Placeholder para ejecución de comandos en Windows."""
    return {"success": False, "message": f"System action '{command_string.split(' ')[0]}' not implemented for Windows yet."}

def shutdown():
    return {"success": False, "message": "Shutdown not implemented for Windows yet."}

def restart():
    return {"success": False, "message": "Restart not implemented for Windows yet."}

def lock_session():
    return {"success": False, "message": "Lock session not implemented for Windows yet."}

def play_pause_media():
    return {"success": False, "message": "Multimedia control not implemented for Windows yet."}

def set_volume(level):
    return {"success": False, "message": "Volume control not implemented for Windows yet."}

def get_cpu_usage():
    return {"success": False, "message": "Metrics not implemented for Windows yet."}

def get_ram_usage():
    return {"success": False, "message": "Metrics not implemented for Windows yet."}

def get_uptime():
    return {"success": False, "message": "Metrics not implemented for Windows yet."}

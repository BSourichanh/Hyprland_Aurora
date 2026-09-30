#!/bin/bash
# Protocole de Verrouillage Sécurisé Hyprland / Aurora Theme
# Support multi-écrans dynamique & protection anti-fuite de workspaces

# Empêcher le lancement si hyprlock tourne déjà
if pidof hyprlock >/dev/null; then
    exit 0
fi

LOCK_FLAG="/tmp/hypr_locked"
STATE_FILE="/tmp/hypr_lock_orig_workspaces.json"

# Poser le drapeau pour neutraliser l'auto-compacteur de workspaces
touch "$LOCK_FLAG"

# Sauvegarde atomique de l'état initial des moniteurs et workspaces
python3 -c '
import os, sys, json, socket
runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
if not runtime_dir or not his: sys.exit(0)
cmd_sock = os.path.join(runtime_dir, "hypr", his, ".socket.sock")
try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(cmd_sock)
        s.sendall(b"j/monitors")
        res = b""
        while True:
            c = s.recv(4096)
            if not c: break
            res += c
    monitors = json.loads(res.decode("utf-8", errors="replace"))
    state = {}
    for m in monitors:
        state[m.get("name")] = m.get("activeWorkspace", {}).get("id")
        if m.get("focused"):
            state["__focused__"] = m.get("name")
    with open("/tmp/hypr_lock_orig_workspaces.json", "w") as f:
        json.dump(state, f)
except Exception:
    pass
' >/dev/null 2>&1

# Basculement initial immédiat vers les espaces vides réservés (98 sur DP-2, 99 sur DP-1)
python3 -c '
import os, sys, json, socket
runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
if not runtime_dir or not his: sys.exit(0)
cmd_sock = os.path.join(runtime_dir, "hypr", his, ".socket.sock")
try:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.connect(cmd_sock)
        s.sendall(b"j/monitors")
        res = b""
        while True:
            c = s.recv(4096)
            if not c: break
            res += c
    monitors = json.loads(res.decode("utf-8", errors="replace"))
    cmds = []
    for m in monitors:
        name = m.get("name")
        if name == "DP-2":
            cmds.append("dispatch focusmonitor DP-2;dispatch workspace 98")
        elif name == "DP-1":
            cmds.append("dispatch focusmonitor DP-1;dispatch workspace 99")
        else:
            cmds.append(f"dispatch focusmonitor {name};dispatch workspace 97")
    if cmds:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(cmd_sock)
            s.sendall(("[[BATCH]]" + ";".join(cmds)).encode("utf-8"))
            s.recv(4096)
except Exception:
    pass
' >/dev/null 2>&1

# Démon d'arrière-plan surveillant le rebranchement / réveil des écrans (hotplug)
python3 - << 'EOF' &
import os, sys, json, socket, time, subprocess, signal

runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
if not runtime_dir or not his:
    sys.exit(0)

base_dir = os.path.join(runtime_dir, "hypr", his)
cmd_sock_path = os.path.join(base_dir, ".socket.sock")
event_sock_path = os.path.join(base_dir, ".socket2.sock")
lock_file = "/tmp/hypr_locked"
tool_path = "/home/user/Documents/antigravity/hyprland_project/scripts/wallpaper_tool.py"

def query(cmd: str) -> str:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(cmd_sock_path)
            s.sendall(cmd.encode("utf-8"))
            chunks = []
            while True:
                data = s.recv(4096)
                if not data: break
                chunks.append(data)
            return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception:
        return ""

def enforce_lock():
    if not os.path.exists(lock_file):
        return
    try:
        raw = query("j/monitors")
        if not raw: return
        monitors = json.loads(raw)
        cmds = []
        for m in monitors:
            name = m.get("name")
            act = m.get("activeWorkspace", {}).get("id")
            if name == "DP-2" and act != 98:
                cmds.append("dispatch focusmonitor DP-2;dispatch workspace 98")
            elif name == "DP-1" and act != 99:
                cmds.append("dispatch focusmonitor DP-1;dispatch workspace 99")
            elif name not in ("DP-1", "DP-2") and act != 97:
                cmds.append(f"dispatch focusmonitor {name};dispatch workspace 97")
        if cmds:
            query("[[BATCH]]" + ";".join(cmds))
    except Exception:
        pass

def handle_signal(sig, frame):
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(event_sock_path)
except Exception:
    sys.exit(1)

buf = ""
while os.path.exists(lock_file):
    try:
        data = s.recv(4096)
        if not data: break
        buf += data.decode("utf-8", errors="replace")
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line: continue
            ev = line.split(">>")[0]
            if ev in ("monitoradded", "monitoraddedv2"):
                time.sleep(0.12)
                enforce_lock()
                if os.path.exists(tool_path):
                    subprocess.Popen([sys.executable, tool_path, "restart"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif ev in ("workspace", "workspacev2", "focusedmon"):
                enforce_lock()
    except Exception:
        break
s.close()
EOF
WATCHER_PID=$!

# Fermer les menus et cartes popups potentiellement ouverts
pkill -x wofi 2>/dev/null
"$HOME/.config/waybar/scripts/spotify-card.py" hide >/dev/null 2>&1 &

# Masquer Waybar pendant le verrouillage et la restaurer au déverrouillage
WAYBAR_WAS_RUNNING=0
if pgrep -x waybar >/dev/null; then
    WAYBAR_WAS_RUNNING=1
    killall -SIGUSR1 waybar 2>/dev/null
    # Laisser le temps à Waybar et GTK de démapper la surface avant que hyprlock ne capture l'écran
    sleep 0.15
fi

# Gestionnaire de nettoyage déterministe (Safe Cleanup / RAII)
CLEANED=0
cleanup() {
    [ "$CLEANED" -eq 1 ] && return
    CLEANED=1

    # 1. Arrêter le watcher d'écrans
    if [ -n "$WATCHER_PID" ]; then
        kill "$WATCHER_PID" 2>/dev/null
        wait "$WATCHER_PID" 2>/dev/null
    fi

    # 2. Supprimer le drapeau de verrouillage
    rm -f "$LOCK_FLAG"

    # 3. Restaurer dynamiquement les workspaces uniquement sur les moniteurs connectés
    python3 -c '
import os, sys, json, socket
runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
if not runtime_dir or not his: sys.exit(0)
cmd_sock = os.path.join(runtime_dir, "hypr", his, ".socket.sock")
def query(cmd):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(cmd_sock)
            s.sendall(cmd.encode("utf-8"))
            chunks = []
            while True:
                data = s.recv(4096)
                if not data: break
                chunks.append(data)
            return b"".join(chunks).decode("utf-8", errors="replace")
    except Exception:
        return ""

state_file = "/tmp/hypr_lock_orig_workspaces.json"
if os.path.exists(state_file):
    try:
        with open(state_file, "r") as f:
            orig = json.load(f)
        raw_m = query("j/monitors")
        monitors = json.loads(raw_m) if raw_m else []
        cmds = []
        focused_mon = orig.get("__focused__")
        for m in monitors:
            name = m.get("name")
            if name in orig and name != "__focused__":
                orig_ws = orig[name]
                cmds.append(f"dispatch focusmonitor {name};dispatch workspace {orig_ws}")
        if focused_mon and any(m.get("name") == focused_mon for m in monitors):
            cmds.append(f"dispatch focusmonitor {focused_mon}")
        if cmds:
            query("[[BATCH]]" + ";".join(cmds))
    except Exception:
        pass
' >/dev/null 2>&1

    # 4. Nettoyage du fichier d'état
    rm -f "$STATE_FILE"

    # 5. Restaurer Waybar si elle était active
    if [ "$WAYBAR_WAS_RUNNING" -eq 1 ]; then
        killall -SIGUSR1 waybar 2>/dev/null
    fi

    # 6. Relancer un auto-compactage différé pour harmoniser la disposition
    python3 "$HOME/.config/hypr/scripts/workspace-autocompact.py" --once >/dev/null 2>&1 &
}

trap cleanup EXIT INT TERM

# Lancer l'écran de verrouillage
hyprlock

# Exécuter le nettoyage à la sortie normale
cleanup


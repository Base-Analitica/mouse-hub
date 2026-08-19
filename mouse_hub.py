#!/usr/bin/env python3
"""
Mouse Hub - Controlador de Mouse Gamer
========================================
Controle DPI, Sensibilidade, Macros e Auto-Clicker para o Logitech G403 HERO
Auto-Clicker funciona APENAS quando Minecraft/Lunar Client esta em foco.

Autor: Codebuff (Freebuff)
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
import fcntl
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# ─── Configuracao ───────────────────────────────────────────────────────────

MOUSE_NAME = "Logitech G403 HERO Gaming Mouse"
MOUSE_VID = 0x046d
MOUSE_PID = 0xc08f
HIDRAW_PATH = "/dev/hidraw0"

# G403 HERO DPI range
DPI_MIN = 100
DPI_MAX = 25600
DPI_STEP = 50

# Presets de DPI comuns para gaming
DPI_PRESETS = {
    "Low (CS:GO AWP)": 400,
    "Medium (FPS Geral)": 800,
    "High (Minecraft PvP)": 1200,
    "Ultra (Flick Shots)": 1600,
    "Max Speed": 25600,
}

# Ponto de retorno para o JSON de configuracao
CONFIG_PATH = Path.home() / "mouse-hub" / "config.json"
MACROS_PATH = Path.home() / "mouse-hub" / "macros.json"


# ─── Gerenciador de DPI via HID++ 2.0 ───────────────────────────────────────

class LogitechHIDPP:
    """Comunicacao com o Logitech G403 HERO via protocolo HID++ 2.0"""

    # HID++ 2.0 report IDs
    SHORT_REPORT_ID = 0x10
    LONG_REPORT_ID = 0x11

    # Feature pages
    PAGE_DPI_SENSOR = 0x05
    PAGE_DPI_AUTH = 0x20

    def __init__(self, hidraw_path=HIDRAW_PATH):
        self.hidraw_path = hidraw_path
        self.fd = None
        self.connected = False
        self.current_dpi = 800  # Default
        self.dpi_feature_index = None

    def connect(self):
        """Abre conexao com o device HID"""
        try:
            self.fd = os.open(self.hidraw_path, os.O_RDWR | os.O_NONBLOCK)
            self.connected = True
            print(f"[HID] Conectado a {self.hidraw_path}")
            self._discover_features()
            return True
        except (PermissionError, FileNotFoundError, OSError) as e:
            print(f"[HID] Nao foi possivel conectar: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Fecha conexao HID"""
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        self.connected = False

    def _discover_features(self):
        """Descobre os feature indexes do mouse"""
        try:
            # Procura feature index para DPI sensor
            for page in [0x05, 0x81]:
                result = self._send_command(
                    function_index=0,
                    data=bytes([0x00, 0x00, 0x00, 0x00, 0x00]),
                    target_feature_page=0x00,  # Root feature
                )
                if result and len(result) >= 2:
                    # Tenta encontrar o feature de DPI
                    idx = self._get_feature_index(0x05)
                    if idx is not None:
                        self.dpi_feature_index = idx
                        print(f"[HID] Feature DPI encontrada no index: {idx}")
                        break
        except Exception as e:
            print(f"[HID] Feature discovery: {e}")

    def _get_feature_index(self, feature_page):
        """Obtem o index de uma feature pelo page number"""
        try:
            # HID++ 2.0: GetFeatureIndex (function 0x00 do root)
            report = bytearray(7)
            report[0] = self.SHORT_REPORT_ID
            report[1] = 0x10 | 0x00  # destination=1, softwareId=0
            report[2] = 0x00  # function index 0
            # feature page in bytes 4-5 (big endian)
            report[4] = (feature_page >> 8) & 0xFF
            report[5] = feature_page & 0xFF

            os.write(self.fd, bytes(report))
            time.sleep(0.05)

            response = os.read(self.fd, 7)
            if response and response[1] == 0x00:  # No error
                return response[3]  # Feature index
        except Exception as e:
            print(f"[HID] get_feature_index({feature_page}): {e}")
        return None

    def _send_command(self, function_index=0, data=bytes(5), target_feature_page=0x05):
        """Envia um comando HID++ 2.0"""
        if not self.connected or self.fd is None:
            return None

        try:
            report = bytearray(7)
            report[0] = self.SHORT_REPORT_ID
            report[1] = 0x10 | (function_index & 0x0F)
            report[2] = function_index >> 4
            for i, b in enumerate(data[:5]):
                report[3 + i] = b

            os.write(self.fd, bytes(report))
            time.sleep(0.03)

            response = os.read(self.fd, 7)
            return response if response else None
        except (OSError, BlockingIOError) as e:
            print(f"[HID] send_command error: {e}")
            return None

    def set_dpi(self, dpi):
        """Define o DPI do mouse via HID++ ou xinput"""
        dpi = max(DPI_MIN, min(DPI_MAX, dpi))
        # Arredonda para o step mais proximo
        dpi = round(dpi / DPI_STEP) * DPI_STEP
        self.current_dpi = dpi

        # Tenta via HID++ primeiro
        if self.dpi_feature_index is not None:
            try:
                report = bytearray(7)
                report[0] = self.SHORT_REPORT_ID
                report[1] = 0x10 | (self.dpi_feature_index & 0x0F)
                report[2] = 0x00  # function index 0 = SetSensorDPI
                # DPI em bytes 3-4 (big endian, 16-bit)
                report[3] = (dpi >> 8) & 0xFF
                report[4] = dpi & 0xFF

                os.write(self.fd, bytes(report))
                time.sleep(0.03)
                print(f"[HID] DPI definido para {dpi} via HID++")
                return True
            except Exception as e:
                print(f"[HID] DPI via HID++ falhou: {e}")

        # Fallback: ajusta sensibilidade via xinput (nao muda DPI real, mas ajusta acel)
        return self.set_sensitivity_from_dpi(dpi)

    def set_sensitivity_from_dpi(self, target_dpi):
        """Ajusta a sensibilidade do xinput baseado no DPI desejado"""
        try:
            mouse_id = self._get_mouse_xinput_id()
            if mouse_id:
                # Mapeia DPI para aceleracao do libinput
                # DPI 800 = acel 0.0 (default)
                # Cada 400 DPI a mais = +0.1 acel
                accel = (target_dpi - 800) / 4000.0
                accel = max(-1.0, min(1.0, accel))
                subprocess.run(
                    ["xinput", "set-prop", str(mouse_id),
                     "libinput Accel Speed", str(accel)],
                    capture_output=True, timeout=5
                )
                print(f"[XINPUT] Aceleracao ajustada para {accel:.3f} (DPI target: {target_dpi})")
                return True
        except Exception as e:
            print(f"[XINPUT] Erro ao ajustar sensibilidade: {e}")
        return False

    def get_sensitivity(self):
        """Obtem a velocidade de aceleracao atual"""
        try:
            mouse_id = self._get_mouse_xinput_id()
            if mouse_id:
                result = subprocess.run(
                    ["xinput", "list-props", str(mouse_id)],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split('\n'):
                    if 'libinput Accel Speed' in line and 'Default' not in line:
                        value = float(line.split(':')[-1].strip())
                        return round((value + 1.0) / 2.0 * 100)  # 0-100 range
        except Exception:
            pass
        return 50  # Default

    def set_sensitivity(self, value):
        """Define sensibilidade (0-100)"""
        mouse_id = self._get_mouse_xinput_id()
        if mouse_id:
            accel = (value / 100.0) * 2.0 - 1.0  # Mapeia 0-100 para -1.0 a 1.0
            try:
                subprocess.run(
                    ["xinput", "set-prop", str(mouse_id),
                     "libinput Accel Speed", f"{accel:.3f}"],
                    capture_output=True, timeout=5
                )
                print(f"[XINPUT] Sensibilidade definida: {value}% (accel: {accel:.3f})")
                return True
            except Exception as e:
                print(f"[XINPUT] Erro: {e}")
        return False

    def _get_mouse_xinput_id(self):
        """Obtem o ID do mouse no xinput"""
        try:
            result = subprocess.run(
                ["xinput", "list"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'G403' in line and 'slave  pointer' in line:
                    # Extrai o id
                    import re
                    match = re.search(r'id=(\d+)', line)
                    if match:
                        return int(match.group(1))
        except Exception:
            pass
        return None


# ─── Macro Recorder/Player ───────────────────────────────────────────────────

class MacroManager:
    """Sistema de macros: gravar, salvar, reproduzir"""

    def __init__(self):
        self.macros = self._load_macros()
        self.recording = False
        self.current_recording = None
        self.record_start_time = 0
        self.recorded_events = []

    def _load_macros(self):
        """Carrega macros salvas"""
        if MACROS_PATH.exists():
            try:
                with open(MACROS_PATH, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_macros(self):
        """Salva macros em disco"""
        try:
            MACROS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MACROS_PATH, 'w') as f:
                json.dump(self.macros, f, indent=2)
        except IOError as e:
            print(f"[MACRO] Erro ao salvar: {e}")

    def start_recording(self, name="macro"):
        """Inicia gravacao de macro"""
        self.recording = True
        self.current_recording = name
        self.record_start_time = time.time()
        self.recorded_events = []
        print(f"[MACRO] Gravando: {name}")
        return True

    def stop_recording(self):
        """Para gravacao e salva"""
        if not self.recording:
            return None
        self.recording = False
        macro_name = self.current_recording
        self.macros[macro_name] = {
            "name": macro_name,
            "events": self.recorded_events,
            "created": datetime.now().isoformat(),
            "count": len(self.recorded_events),
        }
        self._save_macros()
        print(f"[MACRO] Parou gravacao: {macro_name} ({len(self.recorded_events)} eventos)")
        return macro_name

    def add_event(self, event_type, key=None, button=None, x=None, y=None):
        """Adiciona um evento a gravacao atual"""
        if not self.recording:
            return
        elapsed = time.time() - self.record_start_time
        event = {
            "time": round(elapsed, 4),
            "type": event_type,
        }
        if key:
            event["key"] = key
        if button:
            event["button"] = button
        if x is not None:
            event["x"] = x
        if y is not None:
            event["y"] = y
        self.recorded_events.append(event)

    def play_macro(self, name, repeat=1):
        """Reproduz uma macro"""
        if name not in self.macros:
            print(f"[MACRO] Macro '{name}' nao encontrada")
            return False

        macro = self.macros[name]
        events = macro["events"]
        if not events:
            return False

        print(f"[MACRO] Reproduzindo: {name} ({repeat}x)")

        for r in range(repeat):
            prev_time = 0
            for event in events:
                delay = event["time"] - prev_time
                if delay > 0:
                    time.sleep(delay)
                prev_time = event["time"]

                etype = event["type"]
                if etype == "key_press":
                    try:
                        subprocess.run(["xdotool", "key", event["key"]],
                                       capture_output=True, timeout=2)
                    except Exception:
                        pass
                elif etype == "key_release":
                    pass  # xdotool key already handles press+release
                elif etype == "mouse_click":
                    btn = event.get("button", 1)
                    try:
                        subprocess.run(["xdotool", "click", str(btn)],
                                       capture_output=True, timeout=2)
                    except Exception:
                        pass
                elif etype == "mouse_move":
                    x, y = event.get("x", 0), event.get("y", 0)
                    try:
                        subprocess.run(["xdotool", "mousemove", str(x), str(y)],
                                       capture_output=True, timeout=2)
                    except Exception:
                        pass

        print(f"[MACRO] Reproducao concluida: {name}")
        return True

    def delete_macro(self, name):
        """Deleta uma macro"""
        if name in self.macros:
            del self.macros[name]
            self._save_macros()
            return True
        return False

    def list_macros(self):
        """Lista todas as macros"""
        return {name: {
            "name": m["name"],
            "count": m["count"],
            "created": m["created"]
        } for name, m in self.macros.items()}


# ─── Auto-Clicker ───────────────────────────────────────────────────────────

class AutoClicker:
    """Auto-clicker que funciona APENAS quando Minecraft/Lunar Client esta focado"""

    MINECRAFT_WINDOWS = [
        "Minecraft",
        "Lunar Client",
        "Lunar",
        "Badlion",
        "Feather",
        "Hypixel",
        "Minecraft*",
    ]

    def __init__(self):
        self.running = False
        self.thread = None
        self.cps = 10  # Clicks por segundo
        self.button = 1  # 1=left, 2=middle, 3=right
        self.mode = "hold"  # "hold" = segura o botao, "toggle" = liga/desliga com tecla
        self.jitter_ms = 0  # Variacao aleatoria em ms
        self.break_blocks = False  # Modo quebrar blocos (click esquerda)

    def is_minecraft_focused(self):
        """Verifica se Minecraft/Lunar Client esta em foco"""
        try:
            # Obtem a janela ativa
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode != 0:
                return False

            window_id = result.stdout.strip()

            # Obtem o nome da janela
            result = subprocess.run(
                ["xdotool", "getwindowname", window_id],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode != 0:
                return False

            window_name = result.stdout.strip()
            print(f"[AUTOCLICK] Janela ativa: {window_name}")

            # Verifica se e Minecraft ou similar
            for mc_name in self.MINECRAFT_WINDOWS:
                if mc_name.lower() in window_name.lower():
                    return True

            return False
        except Exception as e:
            print(f"[AUTOCLICK] Erro ao detectar janela: {e}")
            return False

    def _click_loop(self):
        """Loop principal do auto-clicker"""
        while self.running:
            if self.is_minecraft_focused():
                try:
                    # Clique via xdotool
                    subprocess.run(
                        ["xdotool", "click", str(self.button)],
                        capture_output=True, timeout=2
                    )
                except Exception:
                    pass

                # Calcula delay com jitter
                delay = 1.0 / self.cps
                if self.jitter_ms > 0:
                    import random
                    jitter = random.uniform(-self.jitter_ms, self.jitter_ms) / 1000.0
                    delay += jitter
                    delay = max(0.001, delay)

                time.sleep(delay)
            else:
                # Se nao esta no Minecraft, espera mais
                time.sleep(0.2)

    def start(self):
        """Inicia o auto-clicker"""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._click_loop, daemon=True)
        self.thread.start()
        print(f"[AUTOCLICK] Iniciado ({self.cps} CPS, botao {self.button})")

    def stop(self):
        """Para o auto-clicker"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[AUTOCLICK] Parado")

    def set_cps(self, cps):
        """Define clicks por segundo"""
        self.cps = max(1, min(50, cps))
        print(f"[AUTOCLICK] CPS: {self.cps}")

    def set_button(self, button):
        """Define qual botao usar (1=left, 2=middle, 3=right)"""
        self.button = button


# ─── Config Manager ──────────────────────────────────────────────────────────

class ConfigManager:
    """Gerencia configuracoes do mouse"""

    def __init__(self):
        self.config = self._load()

    def _load(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "dpi": 800,
            "sensitivity": 50,
            "polling_rate": 1000,
            "lighting": {
                "enabled": True,
                "color": "#FF0000",
                "brightness": 80,
                "mode": "static",
            },
            "profiles": {
                "minecraft": {"dpi": 1200, "sensitivity": 60},
                "csgo": {"dpi": 400, "sensitivity": 30},
                "default": {"dpi": 800, "sensitivity": 50},
            },
        }

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()


# ─── Web Server ──────────────────────────────────────────────────────────────

class MouseHubHandler(SimpleHTTPRequestHandler):
    """Handler HTTP para a interface web"""

    hub = None  # Referencia ao MouseHub principal

    def log_message(self, format, *args):
        # Silencia logs HTTP
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self._serve_index()
        elif path == "/api/status":
            self._json_response(self._get_status())
        elif path == "/api/mouse/dpi":
            self._json_response({"dpi": self.hub.hid.current_dpi})
        elif path == "/api/mouse/sensitivity":
            self._json_response({"sensitivity": self.hub.hid.get_sensitivity()})
        elif path == "/api/macros/list":
            self._json_response(self.hub.macros.list_macros())
        elif path == "/api/autoclicker/status":
            self._json_response({
                "running": self.hub.clicker.running,
                "cps": self.hub.clicker.cps,
                "button": self.hub.clicker.button,
                "minecraft_detected": self.hub.clicker.is_minecraft_focused(),
            })
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}

        if path == "/api/mouse/dpi":
            self._handle_set_dpi(data)
        elif path == "/api/mouse/sensitivity":
            self._handle_set_sensitivity(data)
        elif path == "/api/macros/record/start":
            self._handle_macro_record_start(data)
        elif path == "/api/macros/record/stop":
            self._handle_macro_record_stop(data)
        elif path == "/api/macros/play":
            self._handle_macro_play(data)
        elif path == "/api/macros/delete":
            self._handle_macro_delete(data)
        elif path == "/api/autoclicker/start":
            self._handle_autoclicker_start(data)
        elif path == "/api/autoclicker/stop":
            self._handle_autoclicker_stop()
        elif path == "/api/autoclicker/config":
            self._handle_autoclicker_config(data)
        elif path == "/api/profile/load":
            self._handle_profile_load(data)
        elif path == "/api/profile/save":
            self._handle_profile_save(data)
        else:
            self.send_error(404)

    def _serve_index(self):
        html_path = Path(__file__).parent / "static" / "index.html"
        if html_path.exists():
            content = html_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "index.html not found")

    def _json_response(self, data, status=200):
        content = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(content))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def _get_status(self):
        return {
            "mouse": {
                "name": MOUSE_NAME,
                "connected": self.hub.hid.connected,
                "dpi": self.hub.hid.current_dpi,
                "sensitivity": self.hub.hid.get_sensitivity(),
            },
            "autoclicker": {
                "running": self.hub.clicker.running,
                "cps": self.hub.clicker.cps,
            },
            "macros": self.hub.macros.list_macros(),
            "minecraft_active": self.hub.clicker.is_minecraft_focused(),
        }

    def _handle_set_dpi(self, data):
        dpi = data.get("dpi", 800)
        if self.hub.hid.set_dpi(dpi):
            self.hub.config.set("dpi", dpi)
            self._json_response({"ok": True, "dpi": dpi})
        else:
            self._json_response({"ok": True, "dpi": dpi, "note": "Ajustado via sensibilidade do sistema"})

    def _handle_set_sensitivity(self, data):
        value = data.get("sensitivity", 50)
        if self.hub.hid.set_sensitivity(value):
            self.hub.config.set("sensitivity", value)
            self._json_response({"ok": True, "sensitivity": value})
        else:
            self._json_response({"ok": False}, 500)

    def _handle_macro_record_start(self, data):
        name = data.get("name", f"macro_{int(time.time())}")
        self.hub.macros.start_recording(name)
        self._json_response({"ok": True, "name": name})

    def _handle_macro_record_stop(self, data):
        name = self.hub.macros.stop_recording()
        self._json_response({"ok": True, "name": name})

    def _handle_macro_play(self, data):
        name = data.get("name", "")
        repeat = data.get("repeat", 1)
        # Reproduz em thread separada para nao bloquear
        threading.Thread(
            target=self.hub.macros.play_macro,
            args=(name, repeat),
            daemon=True
        ).start()
        self._json_response({"ok": True})

    def _handle_macro_delete(self, data):
        name = data.get("name", "")
        ok = self.hub.macros.delete_macro(name)
        self._json_response({"ok": ok})

    def _handle_autoclicker_start(self, data):
        self.hub.clicker.start()
        self._json_response({"ok": True})

    def _handle_autoclicker_stop(self, data=None):
        self.hub.clicker.stop()
        self._json_response({"ok": True})

    def _handle_autoclicker_config(self, data):
        if "cps" in data:
            self.hub.clicker.set_cps(data["cps"])
        if "button" in data:
            self.hub.clicker.set_button(data["button"])
        self._json_response({
            "ok": True,
            "cps": self.hub.clicker.cps,
            "button": self.hub.clicker.button,
        })

    def _handle_profile_load(self, data):
        profile_name = data.get("name", "default")
        profiles = self.hub.config.get("profiles", {})
        if profile_name in profiles:
            profile = profiles[profile_name]
            self.hub.hid.set_dpi(profile.get("dpi", 800))
            self.hub.hid.set_sensitivity(profile.get("sensitivity", 50))
            self._json_response({"ok": True, "profile": profile})
        else:
            self._json_response({"ok": False, "error": "Perfil nao encontrado"}, 404)

    def _handle_profile_save(self, data):
        name = data.get("name", "custom")
        profiles = self.hub.config.get("profiles", {})
        profiles[name] = {
            "dpi": self.hub.hid.current_dpi,
            "sensitivity": self.hub.hid.get_sensitivity(),
        }
        self.hub.config.set("profiles", profiles)
        self._json_response({"ok": True})


# ─── Main Hub ────────────────────────────────────────────────────────────────

class MouseHub:
    """Classe principal do Mouse Hub"""

    def __init__(self, port=7777):
        self.port = port
        self.hid = LogitechHIDPP()
        self.macros = MacroManager()
        self.clicker = AutoClicker()
        self.config = ConfigManager()
        self.server = None

    def start(self):
        """Inicia o Mouse Hub"""
        print("=" * 60)
        print("  🖱️  MOUSE HUB - Controlador de Mouse Gamer")
        print("=" * 60)
        print()

        # Conecta ao mouse
        print("[INIT] Conectando ao mouse...")
        self.hid.connect()

        # Carrega configuracao salva
        saved_dpi = self.config.get("dpi", 800)
        self.hid.current_dpi = saved_dpi
        print(f"[INIT] DPI configurado: {saved_dpi}")

        # Inicia servidor web
        MouseHubHandler.hub = self
        self.server = HTTPServer(("0.0.0.0", self.port), MouseHubHandler)

        print(f"[INIT] Servidor web: http://localhost:{self.port}")
        print()
        print("  Abra o navegador para acessar a interface.")
        print("  Auto-Clicker funciona APENAS com Minecraft/Lunar Client focado.")
        print()

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\n[INIT] Encerrando...")
            self.stop()

    def stop(self):
        """Para o Mouse Hub"""
        self.clicker.stop()
        self.hid.disconnect()
        if self.server:
            self.server.shutdown()
        print("[INIT] Mouse Hub encerrado.")


# ─── Entry Point ─────────────────────────────────────────────────────────────

def check_root_hidraw():
    """Verifica acesso ao hidraw e sugere correcao"""
    if not os.path.exists(HIDRAW_PATH):
        print(f"[WARN] {HIDRAW_PATH} nao encontrado.")
        print("[WARN] DPI via HID++ nao estara disponivel.")
        print("[WARN] Sensibilidade do sistema ainda funciona via xinput.")
        return False

    if not os.access(HIDRAW_PATH, os.R_OK | os.W_OK):
        print(f"[WARN] Sem acesso de escrita a {HIDRAW_PATH}")
        print("[WARN] Para controle completo de DPI, rode:")
        print(f"       sudo chmod 666 {HIDRAW_PATH}")
        print("       # Ou crie uma regra udev permanente:")
        udev_rule = 'SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c08f", MODE="0666"'
        print(f"       echo '{udev_rule}' | sudo tee /etc/udev/rules.d/99-logitech-g403.rules")
        print("       sudo udevadm control --reload-rules && sudo udevadm trigger")
        print()
        return False

    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Mouse Hub - Controlador de Mouse Gamer")
    parser.add_argument("--port", type=int, default=7777, help="Porta do servidor web")
    parser.add_argument("--dpi", type=int, default=800, help="DPI inicial")
    args = parser.parse_args()

    # Signal handler
    hub = MouseHub(port=args.port)

    def signal_handler(sig, frame):
        print("\n[INIT] Sinal de interrupcao recebido...")
        hub.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Verifica acessos
    check_root_hidraw()

    # Inicia
    hub.start()

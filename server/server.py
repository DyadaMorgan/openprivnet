# openPrivNet. Author: DyadaMorgan. 21.05.2025
import socket
import threading
import time
import json
import os
import sqlite3
import importlib
from cryptography.fernet import Fernet

# === Configuration ===

def load_config():
    if not os.path.exists('config.json'):
        print("Error: config.json not found.")
        exit(1)
    with open('config.json', 'r') as f:
        return json.load(f)

config = load_config()

# === Encryption ===

if config.get('encryption', True):
    if not os.path.exists(config.get('key_path', '')):
        print("Error: encryption enabled, but key_path not found.")
        exit(1)
    with open(config['key_path'], 'rb') as f:
        key = f.read()
    fernet = Fernet(key)
else:
    fernet = None

# === Global variables ===

clients = []
channel_lock = threading.Lock()
plugin_commands = {}

# === Color parsing ===

def parse_colors(text):
    color_map = {
        '&y': '\033[33m', '&b': '\033[34m', '&r': '\033[31m',
        '&g': '\033[32m', '&w': '\033[37m', '&c': '\033[36m',
        '&m': '\033[35m',
    }
    for code, color in color_map.items():
        text = text.replace(code, color)
    return text + '\033[0m'

# === Database operations ===

def init_db():
    conn = sqlite3.connect('channels.db')
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS channels (name TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

def load_channels():
    conn = sqlite3.connect('channels.db')
    cur = conn.cursor()
    cur.execute("SELECT name FROM channels")
    result = {row[0]: [] for row in cur.fetchall()}
    conn.close()
    return result

# === Channel management ===

def create_channel(name, channels):
    if name in channels:
        return f"Channel #{name} already exists."
    try:
        conn = sqlite3.connect('channels.db')
        cur = conn.cursor()
        cur.execute("INSERT INTO channels (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
        channels[name] = []
        return f"Channel #{name} created."
    except Exception as e:
        return f"Error: {e}"

def delete_channel(name, channels):
    if name not in channels:
        return f"Channel #{name} not found."
    try:
        conn = sqlite3.connect('channels.db')
        cur = conn.cursor()
        cur.execute("DELETE FROM channels WHERE name=?", (name,))
        conn.commit()
        conn.close()
        del channels[name]
        return f"Channel #{name} deleted."
    except Exception as e:
        return f"Error: {e}"

# === Message encryption ===

def send_encrypted(sock, message):
    data = message.encode()
    if fernet:
        data = fernet.encrypt(data)
    sock.sendall(len(data).to_bytes(4, 'big') + data)

def recv_encrypted(sock):
    try:
        length_bytes = sock.recv(4)
        if not length_bytes:
            return None
        length = int.from_bytes(length_bytes, 'big')
        data = sock.recv(length)
        if fernet:
            data = fernet.decrypt(data)
        return data.decode()
    except:
        return None

# === Plugins ===
channels = []

def load_plugins():
    global plugin_commands
    plugin_commands.clear()
    if not os.path.exists('plugins.cfg'):
        print("File plugins.cfg not found.")
        return

    plugin_names = []

    with open('plugins.cfg', 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("plugins"):
                parts = line.split("=")
                if len(parts) == 2:
                    plugin_names = parts[1].strip().split()

    for name in plugin_names:
        try:
            module = importlib.import_module(f"plugins.{name}")
            if hasattr(module, 'init_plugin'):
                # Pass 'channels' and 'globals' to the plugin init function
                module.init_plugin(channels, globals())
                print(f"[+] Plugin '{name}' loaded.")
            else:
                print(f"[!] Plugin '{name}' has no init_plugin function.")
        except Exception as e:
            print(f"[!] Error loading plugin '{name}': {e}")


# === Helper functions ===

def format_message(client, msg):
    timestamp = time.strftime("[%H:%M]")
    channel = client.get('channel', 'No channel')
    nickname = client.get('nickname', '???')
    prefix = client.get('prefix', '')
    ch_colored = f"\033[32m#{channel}\033[0m"
    return f"{timestamp} [{ch_colored}] {prefix} {nickname}: {msg}"

def join_channel(client, name, channels):
    with channel_lock:
        if 'channel' in client:
            return f"You are already in channel #{client['channel']}"
        if name not in channels:
            return f"Channel #{name} does not exist."
        client['channel'] = name
        channels[name].append(client)
        return f"You joined channel #{name}"

def leave_channel(client, channels):
    with channel_lock:
        ch = client.pop('channel', None)
        if ch and client in channels.get(ch, []):
            channels[ch].remove(client)
        return f"You left channel #{ch}" if ch else "You are not in any channel."

def find_client_by_nickname(nick, clients):
    for c in clients:
        if c.get('nickname', '').lower() == nick.lower():
            return c
    return None

# === Clients ===

def handle_client(sock, addr, channels):
    client = {'socket': sock}
    clients.append(client)
    print(f"[+] Connection from {addr}")
    send_encrypted(sock, parse_colors(config['welcome_text']))

    try:
        while True:
            msg = recv_encrypted(sock)
            if not msg:
                break

            if msg.startswith('/'):
                parts = msg.strip().split(' ', 1)
                command = parts[0]
                args = parts[1] if len(parts) > 1 else ''

                if command == '/nick':
                    client['nickname'] = args
                    send_encrypted(sock, f"Nickname set: {args}")
                    continue

                elif command == '/prefix':
                    client['prefix'] = args
                    send_encrypted(sock, f"Prefix set: {args}")
                    continue

                elif command == '/join':
                    send_encrypted(sock, join_channel(client, args, channels))
                    continue

                elif command == '/leave':
                    send_encrypted(sock, leave_channel(client, channels))
                    continue

                elif command == '/who':
                    ch = client.get('channel')
                    if ch:
                        names = [c.get('nickname', '?') for c in channels[ch]]
                        send_encrypted(sock, f"Channel #{ch} members: {', '.join(names)}")
                    else:
                        send_encrypted(sock, "You are not in any channel.")
                    continue

                elif command == '/list':
                    send_encrypted(sock, "Channels list:\n" + "\n".join(f"#{k}" for k in channels))
                    continue

                elif command == '/msg':
                    try:
                        to, message = args.split(' ', 1)
                        target = find_client_by_nickname(to, clients)
                        if target:
                            timestamp = time.strftime("[%H:%M]")
                            from_msg = f"{timestamp} [You ➔ {to}]: {message}"
                            to_msg = f"{timestamp} [{client['nickname']} ➔ You]: {message}"
                            send_encrypted(sock, from_msg)
                            send_encrypted(target['socket'], to_msg)
                        else:
                            send_encrypted(sock, f"User '{to}' not found.")
                    except:
                        send_encrypted(sock, "Format: /msg <nick> <message>")
                    continue

                elif command == '/help':
                    send_encrypted(sock, (
                        "/nick <name>\n/prefix <prefix>\n/join <channel>\n"
                        "/leave\n/who\n/list\n/msg <nick> <text>\n"
                        "/plugin_reload – reload plugins\n/hello – example plugin"
                    ))
                    continue

                elif command == '/plugin_reload':
                    load_plugins()
                    send_encrypted(sock, "Plugins reloaded.")
                    continue

                elif command in plugin_commands:
                    plugin_commands[command](client, args, send_encrypted)
                    continue

                else:
                    send_encrypted(sock, "Unknown command. Type /help")
                    continue

            if not client.get('nickname'):
                send_encrypted(sock, "Set your nickname first with /nick <name>")
                continue
            if 'channel' not in client:
                send_encrypted(sock, "You are not in a channel. Use /join <channel_name>")
                continue

            formatted = format_message(client, msg)
            print(formatted)
            ch = client['channel']
            for other in channels[ch][:]:
                try:
                    send_encrypted(other['socket'], formatted)
                except:
                    other['socket'].close()
                    channels[ch].remove(other)

    except Exception as e:
        print(f"[!] Client error {addr}: {e}")
    finally:
        with channel_lock:
            ch = client.get('channel')
            if ch and client in channels.get(ch, []):
                channels[ch].remove(client)
        sock.close()
        clients.remove(client)
        print(f"[-] Disconnected {addr}")

# === Server start ===

def main():
    init_db()
    global channels
    channels = load_channels()

    load_plugins()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((config['ip'], config['port']))
    sock.listen(10)
    print(f"Server started on {config['ip']}:{config['port']}")

    try:
        while True:
            client_sock, addr = sock.accept()
            threading.Thread(target=handle_client, args=(client_sock, addr, channels), daemon=True).start()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()

import socket
import threading
import time
import json
import os
import re
import sqlite3
import importlib
import importlib.util
import traceback
from cryptography.fernet import Fernet

SERVER_VERSION = "0.9.7"

# === Administration ===

admin_lock = threading.Lock()
WARN_LIMIT = 3

def load_admins():
    if not os.path.exists('admins.json'):
        with open('admins.json', 'w') as f:
            json.dump([], f)
        return []
    with open('admins.json', 'r') as f:
        return json.load(f)

admins = load_admins()

def get_admin_immunity(admin):
    if admin and 'immunity' in admin:
        try:
            return int(admin['immunity'])
        except Exception:
            return 0
    return 0

def is_admin(ip, nickname):
    for a in admins:
        if a['ip'] == ip and a['nick'].lower() == nickname.lower():
            return a
    return None

banip_file = 'banip_users.json'
WARN_COUNTS_FILE = 'warn_counts.json'
warn_counts = {}

def load_banned_ips():
    if not os.path.exists(banip_file):
        return []
    with open(banip_file, 'r') as f:
        return json.load(f)

def save_banned_ips(data):
    with open(banip_file, 'w') as f:
        json.dump(data, f)

def load_warn_counts():
    if not os.path.exists(WARN_COUNTS_FILE):
        return {}
    with open(WARN_COUNTS_FILE, 'r') as f:
        data = json.load(f)
        if not isinstance(data, dict):
            print(f"[!] WARNING: warn_counts.json is corrupted (expected dict, got {type(data)}), overwriting.")
            import shutil
            shutil.move(WARN_COUNTS_FILE, WARN_COUNTS_FILE + ".bak")
            return {}
        return data

def save_warn_counts():
    with open(WARN_COUNTS_FILE, 'w') as f:
        json.dump(warn_counts, f)

banned_ips = load_banned_ips()
warn_counts = load_warn_counts()

def ban_ip(ip, reason, nickname="???"):
    global banned_ips
    banned_ips.append({"ip": ip, "nick": nickname, "reason": reason, "time": time.time()})
    save_banned_ips(banned_ips)

def broadcast_system_message(message):
    for c in clients[:]:
        try:
            if not isinstance(c, dict):
                print(f"[!] Invalid object in clients: {repr(c)}")
                clients.remove(c)
                continue
            send_encrypted(c['socket'], f"[System] {message}")
        except Exception as e:
            print(f"[!] System broadcast error: {e}")
            if c in clients:
                clients.remove(c)

def handle_admin_command(client, command, args, sock):
    admin = is_admin(client.get('addr')[0], client.get('nickname', ''))
    if not admin:
        send_encrypted(sock, "You don't have admin privileges.")
        return

    cmd = command.lower().strip()
    args_split = args.strip().split()

    if cmd == '/ahelp':
        send_encrypted(sock, "/kick <nick> <reason>, /banip <nick> <reason>, /warn <nick>, /bans, /unban <nick>, /plugin_reload")

    elif cmd == '/kick':
        if len(args_split) < 2:
            send_encrypted(sock, "Usage: /kick <nick> <reason>")
            return
        target_nick = args_split[0]
        reason = ' '.join(args_split[1:])
        target = find_client_by_nickname(target_nick, clients)
        if target:
            target_admin = is_admin(target['addr'][0], target.get('nickname', ''))
            if target_admin and get_admin_immunity(target_admin) >= get_admin_immunity(admin):
                send_encrypted(sock, "Cannot kick an admin with equal or higher immunity.")
                return
            send_encrypted(target['socket'], f"You have been kicked. Reason: {reason}")
            target['active'] = False
            with channel_lock:
                ch = target.get('channel')
                if ch and ch in channels and target in channels[ch]:
                    channels[ch].remove(target)
                target.pop('channel', None)
            target['socket'].close()
            if target in clients:
                clients.remove(target)
            send_encrypted(sock, f"User {target_nick} has been kicked.")
            broadcast_system_message(f"Admin {client.get('nickname', '???')} kicked user {target_nick} for reason: {reason}")
        else:
            send_encrypted(sock, "User not found.")

    elif cmd == '/banip':
        if len(args_split) < 2:
            send_encrypted(sock, "Usage: /banip <nick> <reason>")
            return
        target_nick = args_split[0]
        reason = ' '.join(args_split[1:])
        target = find_client_by_nickname(target_nick, clients)
        if target:
            target_admin = is_admin(target['addr'][0], target.get('nickname', ''))
            if target_admin and get_admin_immunity(target_admin) >= get_admin_immunity(admin):
                send_encrypted(sock, "Cannot ban an admin with equal or higher immunity.")
                return
            ip = target['addr'][0]
            ban_ip(ip, reason, target.get('nickname', '???'))
            send_encrypted(target['socket'], f"You have been IP banned. Reason: {reason}")
            target['active'] = False
            with channel_lock:
                ch = target.get('channel')
                if ch and ch in channels and target in channels[ch]:
                    channels[ch].remove(target)
                target.pop('channel', None)
            target['socket'].close()
            if target in clients:
                clients.remove(target)
            send_encrypted(sock, f"User {target_nick} has been IP banned on {ip}.")
            broadcast_system_message(f"Admin {client.get('nickname', '???')} blocked IP address of user {target_nick} ({ip}) for reason: {reason}") 
        else:
            send_encrypted(sock, "User not found.")

    elif cmd == '/warn':
        if len(args_split) != 1:
            send_encrypted(sock, "Usage: /warn <nick>")
            return
        target_nick = args_split[0]
        target = find_client_by_nickname(target_nick, clients)
        if target:
            target_admin = is_admin(target['addr'][0], target.get('nickname', ''))
            if target_admin and get_admin_immunity(target_admin) >= get_admin_immunity(admin):
                send_encrypted(sock, "Cannot warn an admin with equal or higher immunity.")
                return
            ip = target['addr'][0]
            warn_counts[ip] = warn_counts.get(ip, 0) + 1
            save_warn_counts()
            send_encrypted(target['socket'], f"Warning! ({warn_counts[ip]}/{WARN_LIMIT})")
            send_encrypted(sock, f"User {target_nick} has been warned ({warn_counts[ip]}/{WARN_LIMIT}).")
            broadcast_system_message(f"Admin {client.get('nickname', '???')} warned user {target_nick} ({warn_counts[ip]}/{WARN_LIMIT})")
            if warn_counts[ip] >= WARN_LIMIT:
                ban_ip(ip, "Multiple warnings", target.get('nickname', '???'))
                send_encrypted(target['socket'], "You have been banned for multiple warnings.")
                warn_counts.pop(ip)
                save_warn_counts()
                target['active'] = False
                with channel_lock:
                    ch = target.get('channel')
                    if ch and ch in channels and target in channels[ch]:
                        channels[ch].remove(target)
                    target.pop('channel', None)
                target['socket'].close()
                if target in clients:
                    clients.remove(target)
                send_encrypted(sock, f"User {target_nick} has been banned for warnings.")
                broadcast_system_message(f"Admin {client.get('nickname', '???')} blocked IP address of user {target_nick} ({ip}) for exceeding warning limit.")
        else:
            send_encrypted(sock, "User not found.")

    elif cmd == '/bans':
        if not banned_ips:
            send_encrypted(sock, "Ban list is empty.")
        else:
            lines = []
            for idx, ban in enumerate(banned_ips, 1):
                ip = ban.get('ip', '???')
                nick = ban.get('nick', '???')
                reason = ban.get('reason', 'not specified')
                ban_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ban.get('time', 0)))
                lines.append(f"{idx}. {nick} | {ip} | {reason} | {ban_time}")
            bans_text = "\n".join(lines)
            send_encrypted(sock, bans_text)

    elif cmd == '/unban':
        if len(args_split) != 1:
            send_encrypted(sock, "Usage: /unban <nick>")
            return
        target_nick = args_split[0].lower()
        unbanned = False
        for entry in banned_ips[:]:
            if entry.get('nick', '').lower() == target_nick:
                banned_ips.remove(entry)
                save_banned_ips(banned_ips)
                send_encrypted(sock, f"IP {entry.get('ip', '???')} has been unbanned.")
                unbanned = True
                break
        if not unbanned:
            send_encrypted(sock, "User not found or not banned.")

    elif cmd == '/plugin_reload':
        load_plugins()
        send_encrypted(sock, "Plugins reloaded.")

    else:
        send_encrypted(sock, "Unknown command. Use /ahelp for command list.")

def is_banned(ip):
    return any(entry['ip'] == ip for entry in banned_ips)

def load_config():
    if not os.path.exists('config.json'):
        print("Error: config.json not found.")
        exit(1)
    with open('config.json', 'r') as f:
        return json.load(f)

config = load_config()

if config.get('encryption', True):
    if not os.path.exists(config.get('key_path', '')):
        print("Error: encryption enabled but key_path not found.")
        exit(1)
    with open(config['key_path'], 'rb') as f:
        key = f.read()
    fernet = Fernet(key)
else:
    fernet = None

clients = []
channel_lock = threading.Lock()
plugin_commands = {}

def parse_colors(text):
    mc_color_map = {
        '0': '\033[30m', '1': '\033[34m', '2': '\033[32m', '3': '\033[36m',
        '4': '\033[31m', '5': '\033[35m', '6': '\033[33m', '7': '\033[37m',
        '8': '\033[90m', '9': '\033[94m', 'a': '\033[92m', 'b': '\033[96m',
        'c': '\033[91m', 'd': '\033[95m', 'e': '\033[93m', 'f': '\033[97m',
    }
    mc_style_map = {
        'l': '\033[1m', 'o': '\033[3m', 'n': '\033[4m', 'm': '\033[9m',
    }

    i = 0
    result = ''
    while i < len(text):
        if text[i] == '&' and i + 1 < len(text):
            code = text[i+1].lower()
            if code == 'r':
                result += '\033[0m'
                i += 2
                continue
            elif code in mc_color_map:
                result += mc_color_map[code]
                i += 2
                continue
            elif code in mc_style_map:
                result += mc_style_map[code]
                i += 2
                continue
        result += text[i]
        i += 1
    result += '\033[0m'
    return result

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

def send_encrypted(sock, message):
    data = message.encode()
    if fernet:
        data = fernet.encrypt(data)
    try:
        sock.sendall(len(data).to_bytes(4, 'big') + data)
    except Exception as e:
        print(f"[!] Send error: {e}")

def recv_encrypted(sock):
    try:
        length_bytes = sock.recv(4)
        if not length_bytes:
            return None
        length = int.from_bytes(length_bytes, 'big')
        data = b''
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        if fernet:
            data = fernet.decrypt(data)
        return data.decode()
    except Exception as e:
        print(f"[!] Receive error: {e}")
        return None

def load_plugins():
    global plugin_commands
    plugin_commands.clear()
    if not os.path.exists('plugins.cfg'):
        print("plugins.cfg file not found.")
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
                module.init_plugin(channels, globals())
                print(f"[+] Plugin '{name}' loaded.")
            else:
                print(f"[!] Plugin '{name}' doesn't have init_plugin function.")
        except Exception as e:
            print(f"[!] Error loading plugin '{name}': {e}")

def format_message(client, msg):
    timestamp = time.strftime("[%H:%M]")
    channel = client.get('channel', 'No channel')
    nickname = client.get('nickname', '???')
    prefix = client.get('prefix', '')
    ch_colored = f"&2#{channel}&r"

    if nickname == '???':
        nickname_colored = f"&9{nickname}&r"
    else:
        nickname_colored = f"&9{nickname}&r"

    full_msg = f"{timestamp} [{ch_colored}] {prefix} {nickname_colored}: {msg}"
    return full_msg  # <--- ONLY THIS!

def join_channel(client, name, channels):
    with channel_lock:
        if 'channel' in client:
            return f"You're already in channel #{client['channel']}"
        if name not in channels:
            return f"Channel #{name} doesn't exist."
        if not isinstance(client, dict):
            print(f"[!] Attempt to add non-dict to channel {name}: {client}")
            return "Client structure error."
        client['channel'] = name
        channels[name].append(client)
        return f"You joined channel #{name}"

def leave_channel(client, channels):
    with channel_lock:
        ch = client.pop('channel', None)
        if ch and ch in channels and client in channels[ch]:
            channels[ch].remove(client)
        return f"You left channel #{ch}" if ch else "You're not in a channel."

def find_client_by_nickname(nick, clients):
    for c in clients:
        if isinstance(c, dict) and c.get('nickname', '').lower() == nick.lower():
            return c
    return None

def get_admins_in_channel(channel_name, channels):
    nicks = []
    if channel_name in channels:
        for c in channels[channel_name]:
            if isinstance(c, dict):
                admin_info = is_admin(c.get('addr', [''])[0], c.get('nickname', ''))
                if admin_info:
                    nicks.append(c.get('nickname', '?'))
    return nicks

def is_valid_name(name):
    return re.fullmatch(r'[A-Za-z0-9_]{3,16}', name) is not None

def handle_client(sock, addr, channels):
    client = {'socket': sock, 'active': True}
    client['addr'] = addr
    admin_info = is_admin(addr[0], client.get('nickname', ''))
    if admin_info:
        client['prefix'] = admin_info['prefix']

    if is_banned(addr[0]):
        sock.close()
        print(f"[-] Blocked connection from banned IP {addr[0]}")
        return

    # --- Client limit ---
    if len(clients) >= config.get("max_clients", 32):
        try:
            send_encrypted(sock, "Server is full, try again later.")
        except Exception:
            pass
        sock.close()
        print(f"[-] Rejected connection {addr}: client limit reached.")
        return

    clients.append(client)
    print(f"[+] Connection from {addr}")
    send_encrypted(sock, parse_colors(config['welcome_text']))

    try:
        while client['active']:
            msg = recv_encrypted(sock)
            if not msg:
                break

            if msg.startswith('/'):
                parts = msg.strip().split(' ', 1)
                command = parts[0]
                args = parts[1] if len(parts) > 1 else ''

                if command == '/nick':
                    new_nick = args.strip()
                    if not new_nick:
                        send_encrypted(sock, "Usage: /nick <name>")
                        continue
                    if not is_valid_name(new_nick):
                        send_encrypted(sock, "Nick must contain only latin letters and numbers, 3-16 characters.")
                        continue
                    if any(isinstance(c, dict) and c.get('nickname', '').lower() == new_nick.lower() for c in clients):
                        send_encrypted(sock, "Nick is already in use.")
                        continue
                    client['nickname'] = new_nick
                    admin_info = is_admin(addr[0], new_nick)
                    if admin_info:
                        client['prefix'] = admin_info['prefix']
                    else:
                        client['prefix'] = ''
                    send_encrypted(sock, f"Nick set: {new_nick}")
                    continue

                elif command == '/prefix':
                    new_prefix = args.strip()
                    if not is_valid_name(new_prefix):
                        send_encrypted(sock, "Prefix must contain only latin letters and numbers, 3-16 characters.")
                        continue
                    client['prefix'] = new_prefix
                    send_encrypted(sock, f"Prefix set: {new_prefix}")
                    continue

                elif command == '/join':
                    send_encrypted(sock, join_channel(client, args, channels))
                    continue

                elif command == '/leave':
                    send_encrypted(sock, leave_channel(client, channels))
                    continue

                elif command == '/who':
                    ch = client.get('channel')
                    if ch and ch in channels:
                        names = [c.get('nickname', '?') for c in channels[ch] if isinstance(c, dict)]
                        send_encrypted(sock, f"Channel #{ch} members: {', '.join(names)}")
                    else:
                        send_encrypted(sock, "You're not in a channel.")
                    continue

                elif command == '/list':
                    send_encrypted(sock, "Channel list:\n" + "\n".join(f"#{k}" for k in channels))
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
                    except Exception as e:
                        send_encrypted(sock, "Format: /msg <nick> <message>")
                        print(f"[!] /msg error: {e}")
                    continue

                elif command == '/help':
                    send_encrypted(sock, (
                        "/nick <name>\n/prefix <prefix>\n/join <channel>\n"
                        "/leave\n/who\n/list\n/msg <nick> <text>\n"
                        "/version – server version"
                        "\n=== Admin Commands ==="
                        "\n/kick <nick> <reason>\n/banip <nick> <reason>\n/warn <nick>\n/plugin_reload – reload plugins"
                        "\n/admins – list admins in your channel\n"
                    ))
                    continue

                elif command in ['/ahelp', '/kick', '/banip', '/warn', '/bans', '/unban', '/plugin_reload']:
                    handle_admin_command(client, command, args, sock)
                    if not client['active']:
                        break
                    continue

                elif command == '/version':
                    send_encrypted(sock, f"Server version: {SERVER_VERSION}")
                    continue

                elif command == '/admins':
                    ch = client.get('channel')
                    if not ch or ch not in channels:
                        send_encrypted(sock, "You're not in a channel.")
                        continue
                    admin_nicks = get_admins_in_channel(ch, channels)
                    if not admin_nicks:
                        send_encrypted(sock, "No admins in this channel.")
                    else:
                        admins_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(admin_nicks)])
                        send_encrypted(sock, f"Admins in channel #{ch}:\n{admins_list}")
                    continue

                elif command in plugin_commands:
                    plugin_commands[command](client, args, send_encrypted)
                    continue

                else:
                    send_encrypted(sock, "Unknown command. Type /help")
                    continue

            if not client.get('nickname'):
                send_encrypted(sock, "First set your nick with /nick <name>")
                continue
            if 'channel' not in client:
                send_encrypted(sock, "You're not in a channel. Use /join <channel_name>")
                continue

            formatted = format_message(client, msg)
            print(parse_colors(formatted))  # ← now colors will be in terminal!
            ch = client['channel']
            if ch and ch in channels:
                # Protection against garbage in channel list:
                for other in channels[ch][:]:
                    try:
                        if not isinstance(other, dict):
                            print(f"[!] Invalid object in channel {ch}: {repr(other)}")
                            channels[ch].remove(other)
                            continue
                        send_encrypted(other['socket'], formatted)
                    except Exception as e:
                        print(f"[!] Message send error: {e}")
                        try:
                            other['socket'].close()
                        except Exception:
                            pass
                        channels[ch].remove(other)

    except Exception as e:
        print(f"[!] Client error {addr}: {e}")
        traceback.print_exc()
    finally:
        with channel_lock:
            ch = client.get('channel')
            if ch and ch in channels and client in channels[ch]:
                channels[ch].remove(client)
        if client in clients:
            clients.remove(client)
        sock.close()
        print(f"[-] Disconnection from {addr}")

def admin_console(channels):
    while True:
        cmd = input(">> ").strip()
        if cmd.startswith("/create "):
            print(create_channel(cmd[8:], channels))
        elif cmd.startswith("/delete "):
            print(delete_channel(cmd[8:], channels))
        elif cmd == "/list":
            print("Channels:\n" + "\n".join(f"#{c}" for c in channels))
        elif cmd == "/exit":
            print("Shutting down server.")
            os._exit(0)
        else:
            print("Commands: /create /delete /list /exit")

def start_server():
    init_db()
    global channels
    channels = load_channels()
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((config['ip'], config['port']))
    sock.listen(5)
    print(f"Server started on {config['ip']}:{config['port']}")
    load_plugins()

    threading.Thread(target=admin_console, args=(channels,), daemon=True).start()

    while True:
        client_sock, addr = sock.accept()
        threading.Thread(target=handle_client, args=(client_sock, addr, channels), daemon=True).start()

if __name__ == "__main__":
    start_server()
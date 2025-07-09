import sys
import socket
import re
import html
import os

os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(os.path.dirname(__file__), 'platforms')

from cryptography.fernet import Fernet
from PyQt5 import QtWidgets
from PyQt5.QtGui import QTextCursor, QIcon
from PyQt5.QtWidgets import QFileDialog, QTextEdit, QVBoxLayout, QPushButton, QWidget, QLineEdit, QLabel, QTabWidget, QSystemTrayIcon
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtMultimedia import QSound

def strip_ansi_codes(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def strip_mc_codes(text):
    # Убирает все &-коды типа &a, &l, &r и т.п.
    return re.sub(r'&[0-9a-fl-or]', '', text, flags=re.IGNORECASE)

def pn_colors_to_html(text):
    import html, re

    mc_color_map = {
        '0': 'black',        '1': 'darkblue',   '2': 'darkgreen',  '3': 'darkcyan',
        '4': 'darkred',      '5': 'darkmagenta','6': 'goldenrod',  '7': 'gray',
        '8': 'darkgray',     '9': 'blue',       'a': 'green',      'b': 'cyan',
        'c': 'red',          'd': 'magenta',    'e': 'yellow',     'f': 'white'
    }
    mc_style_map = {
        'l': 'font-weight:bold;',
        'o': 'font-style:italic;',
        'n': 'text-decoration:underline;',
        'm': 'text-decoration:line-through;',
    }

    def parse_mc_colors(text):
        result = ''
        style_stack = []
        i = 0
        while i < len(text):
            if text[i] == '&' and i + 1 < len(text):
                code = text[i+1].lower()
                if code == 'r':
                    # Сброс всех стилей — просто закрыть все открытые <span>, НЕ открывать новый!
                    while style_stack:
                        result += '</span>'
                        style_stack.pop()
                    i += 2
                    continue
                elif code in mc_color_map:
                    while style_stack:
                        result += '</span>'
                        style_stack.pop()
                    color = mc_color_map[code]
                    result += f'<span style="color:{color};">'
                    style_stack.append('color')
                    i += 2
                    continue
                elif code in mc_style_map:
                    result += f'<span style="{mc_style_map[code]}">'
                    style_stack.append('style')
                    i += 2
                    continue
            result += html.escape(text[i])
            i += 1
        while style_stack:
            result += '</span>'
            style_stack.pop()
        return result

    ansi_colors = {
        '30': 'black',   '31': 'red',      '32': 'green',   '33': 'yellow',
        '34': 'blue',    '35': 'magenta',  '36': 'cyan',    '37': 'white',
        '90': 'gray',    '91': 'lightcoral', '92': 'lightgreen', '93': 'lightyellow',
        '94': 'lightskyblue', '95': 'violet', '96': 'lightcyan', '97': 'white'
    }
    ansi_styles = {
        '1': 'font-weight:bold;',          # bold
        '4': 'text-decoration: underline;',# underline
        '3': 'font-style: italic;',        # italic
    }

    def parse_ansi(text):
        html_output = ''
        open_tags = []
        ansi_escape = re.compile(r'\033\[(.*?)m')
        pos = 0
        for match in ansi_escape.finditer(text):
            start, end = match.span()
            html_output += text[pos:start]
            codes = match.group(1).split(';')
            while open_tags:
                html_output += '</span>'
                open_tags.pop()
            styles = ''
            for code in codes:
                if code in ansi_colors:
                    styles += f'color: {ansi_colors[code]};'
                elif code in ansi_styles:
                    styles += ansi_styles[code]
            if styles:
                html_output += f'<span style="{styles}">'
                open_tags.append('span')
            pos = end
        html_output += text[pos:]
        while open_tags:
            html_output += '</span>'
            open_tags.pop()
        return html_output
    
    mc_parsed = parse_mc_colors(text)
    ansi_parsed = parse_ansi(mc_parsed)
    return ansi_parsed

class ClientWorker(QThread):
    new_message = pyqtSignal(str)

    def __init__(self, client_socket, fernet=None):
        super().__init__()
        self.client_socket = client_socket
        self.fernet = fernet
        self.encrypted = fernet is not None
        self._running = True

    def run(self):
        while self._running:
            message = self.recv_message()
            if message:
                self.new_message.emit(message)

    def stop(self):
        self._running = False
        self.quit()
        self.wait()

    def recv_message(self):
        try:
            length_bytes = self.client_socket.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, 'big')
            data = self.client_socket.recv(length)
            if self.encrypted:
                try:
                    return self.fernet.decrypt(data).decode()
                except:
                    self.encrypted = False
                    return data.decode(errors='ignore')
            else:
                return data.decode(errors='ignore')
        except:
            return None

class ClientGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("openPrivNet Chat Client v0.9.5")
        self.setGeometry(100, 100, 800, 600)

        self.fernet = None
        self.client_socket = None
        self.worker = None
        self.is_connected = False

        self.layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.tab_connect = QWidget()
        self.tab_about = QWidget()
        self.tabs.addTab(self.tab_connect, "Load Key")
        self.tabs.addTab(self.tab_about, "About")

        self.tab_connect.layout = QVBoxLayout()
        self.label = QLabel("IP:Port")
        self.input_connect = QLineEdit()
        self.input_connect.setPlaceholderText("192.168.1.10:12345")
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_to_server)
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Enter message")
        self.message_input.returnPressed.connect(self.send_message)
        self.btn_load_key = QPushButton("Load Key")
        self.btn_load_key.clicked.connect(self.load_key)

        for widget in [self.label, self.input_connect, self.btn_connect,
                       self.chat_display, self.message_input, self.btn_load_key]:
            self.tab_connect.layout.addWidget(widget)

        self.tab_connect.setLayout(self.tab_connect.layout)

        self.tab_about.layout = QVBoxLayout()
        self.about_label = QLabel("openPrivNet Chat Client v0.9.5")
        self.about_description = QLabel("This is a simple chat client with encrypted messages.")
        self.tab_about.layout.addWidget(self.about_label)
        self.tab_about.layout.addWidget(self.about_description)
        self.tab_about.setLayout(self.tab_about.layout)

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

        self.ringtone = QSound("ringtone.wav")
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))
        self.tray_icon.setVisible(True)

        self.show_ascii_art()
        self.chat_display.resizeEvent = self.auto_scroll_on_resize

    def auto_scroll_on_resize(self, event):
        QTextEdit.resizeEvent(self.chat_display, event)
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum())

    def append_message(self, message_html):
        formatted = f"<div style='white-space: pre-wrap; word-wrap: break-word;'>{message_html}</div>"
        self.chat_display.moveCursor(QTextCursor.End)
        self.chat_display.insertHtml(formatted + "<br>")
        self.scroll_to_bottom()

    def show_ascii_art(self):
        ascii_art = """
        ______        _         _   _        _   
        | ___ \\      (_)       | \\ | |      | |  
        | |_/ / _ __  _ __   __|  \\| |  ___ | |_ 
        |  __/ | '__|| |\\ \\ / /| . ` | / _ \\| __|
        | |    | |   | | \\ V / | |\\  ||  __/| |_ 
        \\_|    |_|   |_|  \\_/  \\_| \\_/ \\___| \\__|

        Welcome to the PrivNet client.
        Enter IP:PORT and load the key.
        Enjoy chatting!
        """
        html_content = f"<div style='white-space: pre-wrap; font-family: monospace; word-wrap: break-word;'>{ascii_art}</div>"
        self.chat_display.insertHtml(html_content + "<br>")

    def load_key(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Key File", "", "Key Files (*.key);;All Files (*)", options=options)
        if filepath:
            with open(filepath, 'r') as f:
                key = f.read().strip()
                self.fernet = Fernet(key.encode())
            self.append_message('<span style="color:green">[+] Key loaded successfully.</span>')

    def connect_to_server(self):
        address = self.input_connect.text().strip()
        try:
            ip, port = address.split(":")
            port = int(port)
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((ip, port))

            self.worker = ClientWorker(self.client_socket, self.fernet)
            self.worker.new_message.connect(self.handle_colored_message)
            self.worker.start()

            self.is_connected = True
            self.toggle_load_key_button()
            self.append_message(f'<span style="color:blue">[+] Connected to {ip}:{port}</span>')

            if self.fernet:
                self.append_message('<span style="color:green">[*] Encryption key loaded. Secure communication.</span>')
            else:
                self.append_message('<span style="color:orange">[!] No key loaded. Unencrypted communication.</span>')

        except Exception as e:
            self.append_message(f'<span style="color:red">[!] Connection error: {e}</span>')

    def send_message(self):
        message = self.message_input.text().strip()
        if message:
            self.send_with_optional_encryption(message)
            self.message_input.clear()

    def send_with_optional_encryption(self, message):
        if self.client_socket:
            try:
                if self.fernet:
                    data = self.fernet.encrypt(message.encode())
                else:
                    data = message.encode()
                self.client_socket.sendall(len(data).to_bytes(4, 'big') + data)
            except Exception as e:
                self.append_message(f'<span style="color:red">[!] Failed to send: {e}</span>')

    def strip_mc_codes(text):
    # Убирает все &-коды типа &a, &l, &r и т.п.
        return re.sub(r'&[0-9a-fl-or]', '', text, flags=re.IGNORECASE)

    def handle_colored_message(self, message):
        html_message = pn_colors_to_html(message)
        self.append_message(html_message)
        self.ringtone.play()

        if QtWidgets.QApplication.applicationState() == Qt.ApplicationInactive:
            clean_message = strip_ansi_codes(message)
            clean_message = strip_mc_codes(clean_message)  # убираем &-коды для уведомлений
            clean_message = html.unescape(clean_message)
            self.tray_icon.showMessage("New message", clean_message, QSystemTrayIcon.Information, 5000)

    def toggle_load_key_button(self):
        self.btn_load_key.setVisible(not self.is_connected)

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = ClientGUI()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
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

# Remove ANSI codes for clean text
def strip_ansi_codes(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# Convert ANSI to HTML
def ansi_to_html(text):
    ansi_color_map = {
        '30': 'black', '31': 'red', '32': 'green', '33': 'orange',
        '34': 'blue', '35': 'magenta', '36': 'cyan', '37': 'white',
    }
    span_opened = False
    def replace_ansi(match):
        nonlocal span_opened
        code = match.group(1)
        color = ansi_color_map.get(code, 'white')
        span_opened = True
        return f'<span style="color:{color}">'
    text = re.sub(r'\033\[(3[0-7])m', replace_ansi, text)
    text = text.replace('\033[0m', '</span>' if span_opened else '')
    return text

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
        self.setWindowTitle("openPrivNet Chat Client v0.9.3")
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

        # Connection
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

        # About tab
        self.tab_about.layout = QVBoxLayout()
        self.about_label = QLabel("openPrivNet Chat Client v0.9.3")
        self.about_description = QLabel("This is a simple chat client with encrypted messages.")
        self.tab_about.layout.addWidget(self.about_label)
        self.tab_about.layout.addWidget(self.about_description)
        self.tab_about.setLayout(self.tab_about.layout)

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

        # Notifications
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

    def handle_colored_message(self, message):
        html_message = ansi_to_html(message)
        self.append_message(html_message)
        self.ringtone.play()

        if QtWidgets.QApplication.applicationState() == Qt.ApplicationInactive:
            clean_message = strip_ansi_codes(message)
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

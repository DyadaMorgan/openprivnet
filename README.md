# 🔐 PrivNet — Secure Minimalist Encrypted IRC

PrivNet is a modern network protocol — a minimalist, fully encrypted alternative to classic IRC protocols. It's designed for communication under limited internet conditions, full isolation, or simply for private, surveillance-free conversations.
## 🧠 What is PrivNet?

## PrivNet is:

  A server and client for IRC-style text communication

  Full end-to-end encryption of all messages

  Minimal dependencies — maximum reliability

  Flexible architecture: works in public networks, mesh networks, over radio, or in fully offline environments (as low as 10 Kbps)

  Ideal for hackers, role-players, autonomous communities, and anyone seeking privacy

## 📡 The openPrivNet Protocol

PrivNet uses its own encrypted text-based TCP protocol. Messages are sent in the format:

4 bytes length (big endian) + message body (possibly encrypted)

If encryption is enabled, it uses Fernet (AES-128-GCM). Example of sending data:

sock.sendall(len(data).to_bytes(4, 'big') + data)

## 📲 Protocol Commands (typed in chat with /)
Command	Purpose
/nick <name>	Set nickname
/prefix <prefix>	Set prefix before nickname
/join <channel>	Join a channel
/leave	Leave current channel
/who	List users in the channel
/list	Show all channels
/msg <nick> <text>	Send a private message
/plugin_reload	Reload plugins
/help	Show help
/version	Server version
/...	Additional plugin commands

## 💬 Message Sending

After setting a nickname and joining a channel, all lines not starting with / are treated as messages and sent to the channel. Message display format:

    [12:00] [#general] DyadaMorgan: Hello

Messages and UI support ANSI color codes (e.g., &g, &r).
## 🔌 Plugin System

  Plugins are stored in the plugins/ folder.

  Active plugins are listed in plugins.cfg.

  Plugins implement init_plugin(channels, globals) and add their own commands.

## 🧱 Database

SQLite is used:

  CREATE TABLE channels(name TEXT PRIMARY KEY);

Channels are stored in channels.db and loaded at startup.
## 🔧 Installation and Launch
## 🪟 Windows:

 Install Python 3.9+

 Press Win+R and enter:

    cmd

## Install dependencies:

    pip install cryptography

## Generate key:

    cd keygen
    python3 keygen.py

## 🖥️ Configure config.json

    {
      "ip": "127.0.0.1", // IP address
      "port": 25151, // Port
      "key_path": "keys/secret.key", // Path to the encryption key
      "encryption": true, // Encryption enabled: 'true', encryption disabled: 'false'
      "welcome_text": "&gWelcome to PrivNet! Type /nick <name> and /join <channel>." // Welcome message
    }

## Launch server:

    python3 server.py

Place secret.key in the keys/ folder.

## Install client dependencies:

    pip install pyqt5

## Launch client:

    cd PrivNet-Client/
    python3 client.py

## 🐧 Linux:

  Install Python 3.9+

  Open terminal with Ctrl+Alt+T

## Install dependencies:

    pip install cryptography

## Launch server:

    python3 server.py

## Generate key:

    cd keygen
    python3 keygen.py

Place secret.key in the keys/ folder.

## Install client dependencies:
  
    pip install pyqt5

Launch client:

    cd PrivNet-Client/
    python3 client.py

## 💻 Client Compilation
## 🪟 Windows:
   
     pip install pyinstaller
     pyinstaller --onefile --windowed client.py

## 🐧 Linux:
Ubuntu / Debian:

    sudo apt update
    sudo apt install python3-pip
    pip3 install --user pyinstaller

Fedora:
  
    sudo dnf install python3-pip
    pip3 install --user pyinstaller

Arch Linux / Manjaro:

    sudo pacman -S python-pip
    pip install --user pyinstaller

## To compile the client:

    pyinstaller --onefile --windowed client.py

The executable will appear in the dist/ folder.
## 🚧 Features

  End-to-end encryption (Fernet AES-128-GCM)

  Multi-channel chat

  Plugin and custom command support

  ANSI color markup

  No logs or message history

## 🧱 Use Cases

  Dial-up connections

  Offline/mesh/radio/Tor/I2P networks

  Post-apocalyptic survival communication

  Regions with restricted freedom of speech

  A private IRC alternative

## 📛 Important

PrivNet does not store logs, history, or backups. Messages are only available to sender and receiver.
## ⚠️ P.S.

The creator of PrivNet is not responsible for any consequences of using this software, including but not limited to: data loss, legal issues, privacy breaches, technical failures, or direct/indirect damages.

Use at your own risk. It’s your responsibility to ensure the legality and safety of using PrivNet in your country, especially where private communication or cryptography is restricted.

  If you support military aggression against Ukraine — do not use this code.
  This project is made by people who stand against war, dictatorship, and for freedom.

## 👥 Contributors Wanted:

  GUI designers (Windows/Linux/Android)

  Client developers (Windows/Linux/Android)

  Enthusiasts to run and test PrivNet on various platforms, including radio module support.

## Thank you for your attention!

🔐 PrivNet — A New Take on Old IRC

PrivNet is a minimalist, secure, and encrypted IRC clone. It keeps the simplicity philosophy of classic IRC protocols but adapts to modern realities: privacy, encryption, and readiness to work in offline or limited networks.

🧠 What is it?

PrivNet is:

 A server and client for text communication in the IRC style.

 Fully encrypted messaging (end-to-end encryption).

 Minimal dependencies, maximum reliability.

 Flexible architecture: works in public networks, mesh networks, poor internet conditions, or complete isolation. (Tested at 10 Kbit/s)

 Suitable for hacker communities, dystopias, role-playing games, or anyone who just wants to chat without surveillance.

🔧 What is it written in?

  PrivNet is written in Python 3 and uses:

  socket for network communication,

  threading or asyncio (depending on implementation),

  cryptography or PyNaCl for encryption,

  minimal dependencies to work even in the poorest environments.

⚙️ Installation and setup

  Install Python 3.9+

  Install dependencies:

    pip install cryptography

 Go to the server folder and start the server:

    python3 server.py

🔐 How to generate a key?

Go to the keygen folder.

Run the script:

    python3 keygen.py

Then put the generated secret.key file into the "keys" folder in the server root directory.

install dependency for client:

    pip install pyqt5

Then put the client ID into the client folder and run the client:

    python3 client.py

Configure the server in config.json:

    {
      "ip": "127.0.0.1",          // Server IP address
      "port": 25151,                    // Server port
      "key_path": "keys/secret.key",   // Path to the secret key
      "encryption": true,               // Enable encryption: true / disable encryption: false
      "welcome_text": "&gWelcome to PrivNet! Type /nick <name> and /join <channel>."  // Welcome message
    }

Note: All messages are transmitted encrypted. Only those who know the key can read them.

💻 How to compile the client on Windows / Linux
🪟 Windows

Install Python 3.9+ from python.org, make sure to check “Add Python to PATH” during installation.

Open Command Prompt (cmd) and install PyInstaller:

    pip install pyinstaller

To compile the client, run:

    pyinstaller --onefile --windowed client.py

--onefile — packages everything into a single executable

--windowed — runs the app without a console window (GUI mode)

After compilation, the executable will appear in the dist folder.

🐧 Linux

Installing PyInstaller

Depends on your distro:

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

Compiling the client

    pyinstaller --onefile --windowed client.py

The executable will appear in the dist folder.

🧱 Where can it be used?

Over dial-up networks.

Inside networks without internet access (e.g. via radio modules, Wi-Fi P2P, Tor, I2P).

In anarchic zones and autonomous communities.

As a secure chat between survivor groups in a post-apocalyptic world.

Future plans include communication via HF radio.

Just as an alternative to regular IRC, but without message interception.

🚧 Features

Encrypted chat

Multiple channels

Notifications and status

Plugin support (extensibility)

📛 Important

PrivNet does not keep logs, records, or backups. Whatever you write is read either by the recipient or by no one.

⚠️ P.S.

If you are a Russian fascist supporting Russian aggression against Ukraine, run this code only on TempleOS.
Yes, that’s what Uncle Morgan said.
For you — a castrated ASCII terminal with God on Alt+F12.

People, please make an Android client. I will be very grateful.

Glory to Ukraine! 🇺🇦

# 🖥️ Local SysPilot

**Local SysPilot** is a cross-platform system control dashboard for managing your own computers **within a local network or VPN**.

With a clean web interface and secure login, it allows you to perform basic system actions like shutting down, locking, or controlling multimedia playback — from another trusted device in your local network.

> ⚠️ This project is not intended for public internet exposure. It is designed for **private LAN or VPN environments** only.

---

## ✨ Features

- 🔐 Secure login system (web-based UI)
- 🔌 Power controls: shutdown, lock, suspend (platform-dependent)
- 🎛️ Multimedia control: play/pause, volume, etc.
- 💻 Cross-platform: works on both **Linux** and **Windows**
- 🧩 Modular backend (easy to extend with custom commands)
- 🌐 Accessible from any device within the same LAN or VPN
- 📊 *(Optional)* System metrics support (CPU/RAM, uptime) – *may or may not be implemented*

---

## 🧩 Roadmap

* [ ] Local system control via web (shutdown, lock)
* [ ] Cross-platform backend (Python for Linux, C++ for Windows)
* [ ] Secure login/token-based authentication
* [ ] Basic Streamlit-based control panel
* [ ] Optional system metrics module
* [ ] Systemd/Windows Service installation helpers

---

## 🛡️ Security Notice

Local SysPilot is meant to be used **only inside trusted networks or over VPN**. Exposing it to the public internet is **not recommended** unless you implement proper reverse proxying and HTTPS.

---

## 📄 License

MIT License — see [LICENSE](./LICENSE) for details.

---

## 🤝 Contributing

Feel free to fork this project, suggest improvements, or open pull requests. Feedback is always welcome!

---

## 📬 Contact

Made with 🐧 and 🪟 by Emir Bruges
GitHub: [emirbruges](https://github.com/emirbruges)


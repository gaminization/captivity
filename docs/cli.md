# 💻 Captivity CLI Reference

The `captivity` CLI provides a powerful interface to manage captive portal logins, plugins, and background services.

> [!TIP]
> Use `captivity [command] --help` for detailed information on a specific subcommand.

## 🛠️ Commands

| Command | Description |
|---|---|
| `login` | Login to a captive portal |
| `probe` | Test connectivity |
| `status` | Show connection status |
| `daemon` | Run reconnect daemon |
| `creds` | Manage credentials |
| `plugins` | Manage plugins and marketplace |
| `networks` | List known networks |
| `tray` | Launch system tray icon |
| `learn` | Manage learned networks |
| `stats` | Show connection statistics |
| `dashboard` | Launch web dashboard |
| `simulate` | Run portal simulator for testing |
| `config` | Manage configuration |
| `daemon-rs` | Launch Rust networking daemon |
| `install` | Install the background systemd service |

## ⚙️ Global Options

| Option | Description |
|---|---|
| `-h, --help` | Show this help message and exit |
| `--version` | Show program's version number and exit |
| `-v, --verbose` | Enable debug output |
| `-q, --quiet` | Suppress output except errors |

## 📚 Examples

### Start Background Daemon
```bash
captivity daemon --network "Airport WiFi"
```

### Check Connectivity
```bash
captivity status
```

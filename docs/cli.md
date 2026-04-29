# Captivity CLI Reference

```text
usage: captivity [-h] [--version] [-v] [-q]
                 {login,probe,status,daemon,creds,plugins,networks,tray,learn,stats,dashboard,simulate,config,daemon-rs}
                 ...

Captivity — Autonomous captive portal login client

positional arguments:
  {login,probe,status,daemon,creds,plugins,networks,tray,learn,stats,dashboard,simulate,config,daemon-rs}
                        Available commands
    login               Login to a captive portal
    probe               Test connectivity
    status              Show connection status
    daemon              Run reconnect daemon
    creds               Manage credentials
    plugins             Manage plugins and marketplace
    networks            List known networks
    tray                Launch system tray icon
    learn               Manage learned networks
    stats               Show connection statistics
    dashboard           Launch web dashboard
    simulate            Run portal simulator for testing
    config              Manage configuration
    daemon-rs           Launch Rust networking daemon

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -v, --verbose         Enable debug output
  -q, --quiet           Suppress output except errors
```

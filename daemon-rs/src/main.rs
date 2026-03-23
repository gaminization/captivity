//! Captivity Daemon — Rust networking core.
//!
//! High-performance daemon for network monitoring, captive portal
//! detection, and event dispatching. Communicates with Python
//! components via Unix domain socket IPC.
//!
//! Usage:
//!     captivity-daemon [OPTIONS]
//!
//! Options:
//!     --socket <PATH>     IPC socket path
//!     --probe-url <URL>   Connectivity probe URL
//!     --interval <SECS>   Poll interval in seconds
//!     --timeout <MS>      Probe timeout in milliseconds

mod ipc;
mod monitor;
mod probe;

use ipc::{IpcCommand, IpcServer};
use monitor::{MonitorConfig, MonitorEvent, NetworkMonitor};
use probe::ProbeConfig;
use std::sync::mpsc;
use std::time::Duration;

/// Parse command-line arguments (minimal, no external deps).
struct Args {
    socket_path: Option<String>,
    probe_url: Option<String>,
    interval_secs: Option<u64>,
    timeout_ms: Option<u64>,
}

impl Args {
    fn parse() -> Self {
        let args: Vec<String> = std::env::args().collect();
        let mut result = Self {
            socket_path: None,
            probe_url: None,
            interval_secs: None,
            timeout_ms: None,
        };

        let mut i = 1;
        while i < args.len() {
            match args[i].as_str() {
                "--socket" if i + 1 < args.len() => {
                    result.socket_path = Some(args[i + 1].clone());
                    i += 2;
                }
                "--probe-url" if i + 1 < args.len() => {
                    result.probe_url = Some(args[i + 1].clone());
                    i += 2;
                }
                "--interval" if i + 1 < args.len() => {
                    result.interval_secs = args[i + 1].parse().ok();
                    i += 2;
                }
                "--timeout" if i + 1 < args.len() => {
                    result.timeout_ms = args[i + 1].parse().ok();
                    i += 2;
                }
                "--help" | "-h" => {
                    eprintln!("captivity-daemon — Rust networking core for Captivity");
                    eprintln!();
                    eprintln!("Usage: captivity-daemon [OPTIONS]");
                    eprintln!();
                    eprintln!("Options:");
                    eprintln!("  --socket <PATH>     IPC socket path");
                    eprintln!("  --probe-url <URL>   Connectivity probe URL");
                    eprintln!("  --interval <SECS>   Poll interval (default: 30)");
                    eprintln!("  --timeout <MS>       Probe timeout ms (default: 5000)");
                    eprintln!("  --help, -h           Show this help");
                    std::process::exit(0);
                }
                "--version" | "-V" => {
                    eprintln!("captivity-daemon 2.0.0");
                    std::process::exit(0);
                }
                other => {
                    eprintln!("Unknown argument: {}", other);
                    std::process::exit(1);
                }
            }
        }

        result
    }
}

fn main() {
    let args = Args::parse();

    eprintln!("captivity-daemon v2.0.0 starting...");

    // Build probe config
    let mut probe_config = ProbeConfig::default();
    if let Some(url) = args.probe_url {
        probe_config.url = url;
    }
    if let Some(ms) = args.timeout_ms {
        probe_config.timeout_ms = ms;
    }

    // Build monitor config
    let mut monitor_config = MonitorConfig::default();
    monitor_config.probe = probe_config;
    if let Some(secs) = args.interval_secs {
        monitor_config.poll_interval = Duration::from_secs(secs);
    }

    // IPC channel for commands from clients
    let (cmd_tx, cmd_rx) = mpsc::channel::<IpcCommand>();

    // Socket path
    let socket_path = args
        .socket_path
        .map(std::path::PathBuf::from)
        .unwrap_or_else(ipc::default_socket_path);

    // Start IPC server
    let ipc_server = match IpcServer::new(socket_path, cmd_tx) {
        Ok(server) => server,
        Err(e) => {
            eprintln!("[error] Failed to start IPC server: {}", e);
            std::process::exit(1);
        }
    };

    eprintln!("[daemon] IPC socket: {}", ipc_server.socket_path().display());

    // Create monitor
    let mut monitor = NetworkMonitor::new(monitor_config);
    monitor.set_running(true);

    eprintln!("[daemon] Monitor started, entering event loop...");

    // Main event loop
    let poll_sleep = Duration::from_millis(500);

    while monitor.is_running() {
        // Check for IPC commands
        let commands = ipc_server.poll(monitor.status());
        for cmd in commands {
            match cmd {
                IpcCommand::Stop => {
                    eprintln!("[daemon] Stop command received");
                    monitor.set_running(false);
                }
                IpcCommand::Probe => {
                    eprintln!("[daemon] Manual probe requested");
                    let events = monitor.poll();
                    for event in &events {
                        eprintln!("[daemon] Event: {:?}", event);
                        ipc_server.broadcast_event(event);
                    }
                }
                IpcCommand::Status | IpcCommand::Subscribe => {
                    // Handled in IPC poll
                }
            }
        }

        // Check buffered channel commands
        while let Ok(cmd) = cmd_rx.try_recv() {
            if matches!(cmd, IpcCommand::Stop) {
                monitor.set_running(false);
            }
        }

        // Periodic probe
        if monitor.is_running() && monitor.should_poll() {
            let events = monitor.poll();
            for event in &events {
                match event {
                    MonitorEvent::ProbeComplete(_) => {
                        // Quiet for routine probes
                    }
                    _ => {
                        eprintln!("[daemon] Event: {:?}", event);
                    }
                }
                ipc_server.broadcast_event(event);
            }
        }

        // Sleep between polls
        std::thread::sleep(poll_sleep);
    }

    eprintln!("[daemon] Shutting down...");
}

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
//!     --port <PORT>       IPC TCP port (default: 8788)
//!     --probe-url <URL>   Connectivity probe URL
//!     --interval <SECS>   Poll interval in seconds
//!     --timeout <MS>      Probe timeout in milliseconds

mod ipc;
mod monitor;
mod probe;

use ipc::{IpcCommand, IpcServer};
use monitor::{MonitorConfig, MonitorEvent, NetworkMonitor};
use probe::{ProbeConfig, ConnectivityStatus};
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::{mpsc, RwLock};
use tokio::time::interval;

/// Parse command-line arguments (minimal, no external deps).
struct Args {
    port: Option<u16>,
    probe_url: Option<String>,
    interval_secs: Option<u64>,
    timeout_ms: Option<u64>,
}

impl Args {
    fn parse() -> Self {
        let args: Vec<String> = std::env::args().collect();
        let mut result = Self {
            port: None,
            probe_url: None,
            interval_secs: None,
            timeout_ms: None,
        };

        let mut i = 1;
        while i < args.len() {
            match args[i].as_str() {
                "--port" if i + 1 < args.len() => {
                    result.port = args[i + 1].parse().ok();
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
                    eprintln!("  --port <PORT>       IPC TCP port (default: 8788)");
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

#[tokio::main]
async fn main() {
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
    let poll_interval = args.interval_secs.map(Duration::from_secs).unwrap_or(monitor_config.poll_interval);
    monitor_config.poll_interval = poll_interval;

    // Shared status for IPC
    let current_status = Arc::new(RwLock::new(ConnectivityStatus::NetworkUnavailable));

    // IPC channel for commands from clients
    let (cmd_tx, mut cmd_rx) = mpsc::channel::<IpcCommand>(32);

    // IPC port
    let port = args.port.unwrap_or_else(ipc::default_port);

    // Start IPC server
    let mut ipc_server = match IpcServer::new(port, cmd_tx, current_status.clone()).await {
        Ok(server) => server,
        Err(e) => {
            eprintln!("[error] Failed to start IPC server: {}", e);
            std::process::exit(1);
        }
    };

    eprintln!("[daemon] IPC socket: 127.0.0.1:{}", ipc_server.port());

    // Spawn IPC background listener
    let ipc_server_arc = Arc::new(tokio::sync::RwLock::new(ipc_server));
    let ipc_clone = ipc_server_arc.clone();
    tokio::spawn(async move {
        let mut server = ipc_clone.write().await;
        server.run().await;
    });

    // Create monitor
    let mut monitor = NetworkMonitor::new(monitor_config);
    monitor.set_running(true);

    eprintln!("[daemon] Monitor started, entering event loop...");

    let mut poll_timer = interval(poll_interval);
    // Tick once immediately to align start time, but do the actual first poll manually
    poll_timer.tick().await;

    // Perform initial poll
    let events = monitor.poll().await;
    for event in &events {
        eprintln!("[daemon] Event: {:?}", event);
        ipc_server_arc.read().await.broadcast_event(event).await;
    }
    {
        let mut status = current_status.write().await;
        *status = monitor.status().clone();
    }

    while monitor.is_running() {
        tokio::select! {
            _ = poll_timer.tick() => {
                if monitor.is_running() {
                    let events = monitor.poll().await;
                    
                    // Update shared status
                    {
                        let mut status = current_status.write().await;
                        *status = monitor.status().clone();
                    }

                    // Broadcast
                    let server = ipc_server_arc.read().await;
                    for event in &events {
                        match event {
                            MonitorEvent::ProbeComplete(_) => {}
                            _ => eprintln!("[daemon] Event: {:?}", event),
                        }
                        server.broadcast_event(event).await;
                    }
                }
            }
            Some(cmd) = cmd_rx.recv() => {
                match cmd {
                    IpcCommand::Stop => {
                        eprintln!("[daemon] Stop command received");
                        monitor.set_running(false);
                    }
                    IpcCommand::Probe => {
                        eprintln!("[daemon] Manual probe requested");
                        let events = monitor.poll().await;
                        
                        // Update shared status
                        {
                            let mut status = current_status.write().await;
                            *status = monitor.status().clone();
                        }

                        let server = ipc_server_arc.read().await;
                        for event in &events {
                            eprintln!("[daemon] Event: {:?}", event);
                            server.broadcast_event(event).await;
                        }
                        
                        // Reset timer since we just probed
                        poll_timer.reset();
                    }
                    _ => {}
                }
            }
        }
    }

    eprintln!("[daemon] Shutting down...");
}

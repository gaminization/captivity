//! Unix domain socket IPC server.
//!
//! Provides JSON-based communication between the Rust daemon
//! and Python clients (CLI, bridge, dashboard).
//!
//! Protocol:
//!   Client → Daemon: JSON command + newline
//!   Daemon → Client: JSON response + newline
//!
//! Commands: "status", "probe", "stop"

use crate::monitor::MonitorEvent;
use crate::probe::ConnectivityStatus;
use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread;

/// IPC command from client.
#[derive(Debug, Deserialize)]
#[serde(tag = "command")]
pub enum IpcCommand {
    #[serde(rename = "status")]
    Status,
    #[serde(rename = "probe")]
    Probe,
    #[serde(rename = "stop")]
    Stop,
    #[serde(rename = "subscribe")]
    Subscribe,
}

/// IPC response to client.
#[derive(Debug, Serialize)]
pub struct IpcResponse {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event: Option<MonitorEvent>,
}

impl IpcResponse {
    pub fn ok(message: &str) -> Self {
        Self {
            ok: true,
            status: None,
            message: Some(message.to_string()),
            event: None,
        }
    }

    pub fn status(status: &ConnectivityStatus) -> Self {
        let status_str = match status {
            ConnectivityStatus::Connected => "connected",
            ConnectivityStatus::PortalDetected => "portal_detected",
            ConnectivityStatus::NetworkUnavailable => "network_unavailable",
        };
        Self {
            ok: true,
            status: Some(status_str.to_string()),
            message: None,
            event: None,
        }
    }

    pub fn error(message: &str) -> Self {
        Self {
            ok: false,
            status: None,
            message: Some(message.to_string()),
            event: None,
        }
    }

    pub fn with_event(event: MonitorEvent) -> Self {
        Self {
            ok: true,
            status: None,
            message: None,
            event: Some(event),
        }
    }
}

/// Default socket path.
pub fn default_socket_path() -> PathBuf {
    let runtime_dir = std::env::var("XDG_RUNTIME_DIR")
        .unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(runtime_dir).join("captivity-daemon.sock")
}

/// IPC server managing Unix socket connections.
pub struct IpcServer {
    socket_path: PathBuf,
    listener: Option<UnixListener>,
    command_tx: mpsc::Sender<IpcCommand>,
    subscribers: Arc<Mutex<Vec<UnixStream>>>,
}

impl IpcServer {
    /// Create a new IPC server.
    pub fn new(
        socket_path: PathBuf,
        command_tx: mpsc::Sender<IpcCommand>,
    ) -> std::io::Result<Self> {
        // Remove stale socket
        if socket_path.exists() {
            std::fs::remove_file(&socket_path)?;
        }

        // Create parent directory
        if let Some(parent) = socket_path.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let listener = UnixListener::bind(&socket_path)?;
        listener.set_nonblocking(true)?;

        eprintln!("[ipc] Listening on {}", socket_path.display());

        Ok(Self {
            socket_path,
            listener: Some(listener),
            command_tx,
            subscribers: Arc::new(Mutex::new(Vec::new())),
        })
    }

    /// Accept pending connections and process commands.
    /// Returns any commands received from clients.
    pub fn poll(&self, current_status: &ConnectivityStatus) -> Vec<IpcCommand> {
        let mut commands = Vec::new();

        if let Some(ref listener) = self.listener {
            // Accept new connections
            loop {
                match listener.accept() {
                    Ok((stream, _addr)) => {
                        let cmds = self.handle_client(stream, current_status);
                        commands.extend(cmds);
                    }
                    Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => break,
                    Err(e) => {
                        eprintln!("[ipc] Accept error: {}", e);
                        break;
                    }
                }
            }
        }

        commands
    }

    /// Handle a single client connection.
    fn handle_client(
        &self,
        stream: UnixStream,
        current_status: &ConnectivityStatus,
    ) -> Vec<IpcCommand> {
        let mut commands = Vec::new();

        // Set a short read timeout for non-blocking behavior
        let _ = stream.set_read_timeout(Some(std::time::Duration::from_millis(100)));

        let mut reader = BufReader::new(stream.try_clone().unwrap_or_else(|_| {
            // Fallback — this shouldn't happen with Unix sockets
            panic!("Failed to clone Unix stream");
        }));
        let mut writer = stream;

        let mut line = String::new();
        match reader.read_line(&mut line) {
            Ok(0) => {} // EOF
            Ok(_) => {
                let line = line.trim();
                match serde_json::from_str::<IpcCommand>(line) {
                    Ok(cmd) => {
                        let response = match &cmd {
                            IpcCommand::Status => IpcResponse::status(current_status),
                            IpcCommand::Probe => IpcResponse::ok("probe_requested"),
                            IpcCommand::Stop => IpcResponse::ok("stopping"),
                            IpcCommand::Subscribe => {
                                // Add to subscribers for event streaming
                                if let Ok(clone) = writer.try_clone() {
                                    if let Ok(mut subs) = self.subscribers.lock() {
                                        subs.push(clone);
                                    }
                                }
                                IpcResponse::ok("subscribed")
                            }
                        };

                        if let Ok(json) = serde_json::to_string(&response) {
                            let _ = writeln!(writer, "{}", json);
                        }

                        commands.push(cmd);
                    }
                    Err(e) => {
                        let response = IpcResponse::error(&format!("Invalid command: {}", e));
                        if let Ok(json) = serde_json::to_string(&response) {
                            let _ = writeln!(writer, "{}", json);
                        }
                    }
                }
            }
            Err(_) => {} // Timeout or error
        }

        commands
    }

    /// Broadcast an event to all subscribers.
    pub fn broadcast_event(&self, event: &MonitorEvent) {
        if let Ok(mut subscribers) = self.subscribers.lock() {
            let response = IpcResponse::with_event(event.clone());
            if let Ok(json) = serde_json::to_string(&response) {
                subscribers.retain(|stream| {
                    let mut writer = stream;
                    writeln!(writer, "{}", json).is_ok()
                });
            }
        }
    }

    /// Get the socket path.
    pub fn socket_path(&self) -> &Path {
        &self.socket_path
    }
}

impl Drop for IpcServer {
    fn drop(&mut self) {
        // Clean up socket file
        let _ = std::fs::remove_file(&self.socket_path);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_socket_path() {
        let path = default_socket_path();
        assert!(path.to_string_lossy().contains("captivity-daemon.sock"));
    }

    #[test]
    fn test_ipc_command_deserialize() {
        let cmd: IpcCommand = serde_json::from_str(r#"{"command": "status"}"#).unwrap();
        assert!(matches!(cmd, IpcCommand::Status));

        let cmd: IpcCommand = serde_json::from_str(r#"{"command": "probe"}"#).unwrap();
        assert!(matches!(cmd, IpcCommand::Probe));

        let cmd: IpcCommand = serde_json::from_str(r#"{"command": "stop"}"#).unwrap();
        assert!(matches!(cmd, IpcCommand::Stop));
    }

    #[test]
    fn test_ipc_response_serialize() {
        let resp = IpcResponse::ok("test");
        let json = serde_json::to_string(&resp).unwrap();
        assert!(json.contains("\"ok\":true"));
        assert!(json.contains("\"test\""));
    }

    #[test]
    fn test_ipc_status_response() {
        let resp = IpcResponse::status(&ConnectivityStatus::Connected);
        let json = serde_json::to_string(&resp).unwrap();
        assert!(json.contains("\"connected\""));
    }

    #[test]
    fn test_ipc_error_response() {
        let resp = IpcResponse::error("bad command");
        let json = serde_json::to_string(&resp).unwrap();
        assert!(json.contains("\"ok\":false"));
    }
}

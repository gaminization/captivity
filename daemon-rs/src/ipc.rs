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
use std::sync::Arc;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{mpsc, Mutex, RwLock};

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

/// Default IPC port.
pub fn default_port() -> u16 {
    8788
}

/// IPC server managing TCP connections.
pub struct IpcServer {
    port: u16,
    listener: Option<TcpListener>,
    command_tx: mpsc::Sender<IpcCommand>,
    subscribers: Arc<Mutex<Vec<TcpStream>>>,
    current_status: Arc<RwLock<ConnectivityStatus>>,
}

impl IpcServer {
    /// Create a new IPC server.
    pub async fn new(
        port: u16,
        command_tx: mpsc::Sender<IpcCommand>,
        current_status: Arc<RwLock<ConnectivityStatus>>,
    ) -> std::io::Result<Self> {
        let addr = format!("127.0.0.1:{}", port);
        let listener = TcpListener::bind(&addr).await?;

        eprintln!("[ipc] Listening on {}", addr);

        Ok(Self {
            port,
            listener: Some(listener),
            command_tx,
            subscribers: Arc::new(Mutex::new(Vec::new())),
            current_status,
        })
    }

    /// Accept pending connections and process commands asynchronously.
    pub async fn run(&mut self) {
        if let Some(listener) = self.listener.take() {
            loop {
                match listener.accept().await {
                    Ok((stream, _addr)) => {
                        let cmd_tx = self.command_tx.clone();
                        let status = self.current_status.clone();
                        let subs = self.subscribers.clone();
                        
                        tokio::spawn(async move {
                            Self::handle_client(stream, status, cmd_tx, subs).await;
                        });
                    }
                    Err(e) => {
                        eprintln!("[ipc] Accept error: {}", e);
                    }
                }
            }
        }
    }

    /// Handle a single client connection.
    async fn handle_client(
        mut stream: TcpStream,
        current_status: Arc<RwLock<ConnectivityStatus>>,
        command_tx: mpsc::Sender<IpcCommand>,
        subscribers: Arc<Mutex<Vec<TcpStream>>>,
    ) {
        let (reader, mut writer) = stream.split();
        let mut reader = BufReader::new(reader);
        let mut line = String::new();

        match reader.read_line(&mut line).await {
            Ok(0) => {} // EOF
            Ok(_) => {
                let line = line.trim();
                match serde_json::from_str::<IpcCommand>(line) {
                    Ok(cmd) => {
                        let is_subscribe = matches!(cmd, IpcCommand::Subscribe);
                        let is_probe = matches!(cmd, IpcCommand::Probe);
                        let is_stop = matches!(cmd, IpcCommand::Stop);
                        
                        let response = match &cmd {
                            IpcCommand::Status => {
                                let status = current_status.read().await;
                                IpcResponse::status(&*status)
                            }
                            IpcCommand::Probe => IpcResponse::ok("probe_requested"),
                            IpcCommand::Stop => IpcResponse::ok("stopping"),
                            IpcCommand::Subscribe => {
                                IpcResponse::ok("subscribed")
                            }
                        };

                        if let Ok(json) = serde_json::to_string(&response) {
                            let _ = writer.write_all(format!("{}\n", json).as_bytes()).await;
                        }

                        // Forward command to main loop
                        if is_probe || is_stop {
                            let _ = command_tx.send(cmd).await;
                        }

                        if is_subscribe {
                            // Reassemble stream and add to subscribers
                            let mut stream = reader.into_inner().unsplit(writer);
                            let mut subs = subscribers.lock().await;
                            subs.push(stream);
                        }
                    }
                    Err(e) => {
                        let response = IpcResponse::error(&format!("Invalid command: {}", e));
                        if let Ok(json) = serde_json::to_string(&response) {
                            let _ = writer.write_all(format!("{}\n", json).as_bytes()).await;
                        }
                    }
                }
            }
            Err(_) => {} // Timeout or error
        }
    }

    /// Broadcast an event to all subscribers.
    pub async fn broadcast_event(&self, event: &MonitorEvent) {
        let mut subscribers = self.subscribers.lock().await;
        if subscribers.is_empty() {
            return;
        }

        let response = IpcResponse::with_event(event.clone());
        if let Ok(json) = serde_json::to_string(&response) {
            let message = format!("{}\n", json);
            let bytes = message.as_bytes();
            
            // Keep streams that successfully write
            let mut keep = Vec::new();
            for mut stream in subscribers.drain(..) {
                if stream.write_all(bytes).await.is_ok() {
                    keep.push(stream);
                }
            }
            *subscribers = keep;
        }
    }

    /// Get the bound port.
    pub fn port(&self) -> u16 {
        self.port
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_port() {
        assert_eq!(default_port(), 8788);
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

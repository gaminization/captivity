//! Network state monitor.
//!
//! Polls connectivity at configurable intervals and tracks
//! state transitions (Connected ↔ PortalDetected ↔ Unavailable).

use crate::probe::{probe_connectivity, ConnectivityStatus, ProbeConfig, ProbeResult};
use serde::{Deserialize, Serialize};
use std::time::{Duration, Instant};

/// Events emitted by the monitor on state changes.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "event", content = "data")]
pub enum MonitorEvent {
    /// Network connectivity established.
    NetworkConnected { latency_ms: u64 },
    /// Captive portal detected.
    PortalDetected { redirect_url: Option<String> },
    /// Network became unavailable.
    NetworkUnavailable,
    /// Session expired (was connected, now portal/unavailable).
    SessionExpired,
    /// Probe completed (periodic heartbeat).
    ProbeComplete(ProbeResult),
}

/// Configuration for the network monitor.
#[derive(Debug, Clone)]
pub struct MonitorConfig {
    pub probe: ProbeConfig,
    pub poll_interval: Duration,
}

impl Default for MonitorConfig {
    fn default() -> Self {
        Self {
            probe: ProbeConfig::default(),
            poll_interval: Duration::from_secs(30),
        }
    }
}

/// Network state monitor that tracks connectivity changes.
pub struct NetworkMonitor {
    config: MonitorConfig,
    last_status: ConnectivityStatus,
    last_probe: Option<Instant>,
    running: bool,
}

impl NetworkMonitor {
    /// Create a new monitor with the given configuration.
    pub fn new(config: MonitorConfig) -> Self {
        Self {
            config,
            last_status: ConnectivityStatus::NetworkUnavailable,
            last_probe: None,
            running: false,
        }
    }

    /// Run a single probe cycle and return any state-change events.
    pub fn poll(&mut self) -> Vec<MonitorEvent> {
        let result = probe_connectivity(&self.config.probe);
        let mut events = vec![MonitorEvent::ProbeComplete(result.clone())];

        // Detect state transitions
        if result.status != self.last_status {
            match (&self.last_status, &result.status) {
                (_, ConnectivityStatus::Connected) => {
                    events.push(MonitorEvent::NetworkConnected {
                        latency_ms: result.latency_ms,
                    });
                }
                (ConnectivityStatus::Connected, ConnectivityStatus::PortalDetected) => {
                    events.push(MonitorEvent::SessionExpired);
                    events.push(MonitorEvent::PortalDetected {
                        redirect_url: result.redirect_url.clone(),
                    });
                }
                (ConnectivityStatus::Connected, ConnectivityStatus::NetworkUnavailable) => {
                    events.push(MonitorEvent::SessionExpired);
                    events.push(MonitorEvent::NetworkUnavailable);
                }
                (_, ConnectivityStatus::PortalDetected) => {
                    events.push(MonitorEvent::PortalDetected {
                        redirect_url: result.redirect_url.clone(),
                    });
                }
                (_, ConnectivityStatus::NetworkUnavailable) => {
                    events.push(MonitorEvent::NetworkUnavailable);
                }
            }
            self.last_status = result.status;
        }

        self.last_probe = Some(Instant::now());
        events
    }

    /// Check if it's time for the next poll.
    pub fn should_poll(&self) -> bool {
        match self.last_probe {
            None => true,
            Some(last) => last.elapsed() >= self.config.poll_interval,
        }
    }

    /// Get the current connectivity status.
    pub fn status(&self) -> &ConnectivityStatus {
        &self.last_status
    }

    /// Set running flag.
    pub fn set_running(&mut self, running: bool) {
        self.running = running;
    }

    /// Check if monitor is running.
    pub fn is_running(&self) -> bool {
        self.running
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_monitor_config_defaults() {
        let config = MonitorConfig::default();
        assert_eq!(config.poll_interval, Duration::from_secs(30));
    }

    #[test]
    fn test_monitor_initial_state() {
        let monitor = NetworkMonitor::new(MonitorConfig::default());
        assert_eq!(*monitor.status(), ConnectivityStatus::NetworkUnavailable);
        assert!(!monitor.is_running());
    }

    #[test]
    fn test_should_poll_initially() {
        let monitor = NetworkMonitor::new(MonitorConfig::default());
        assert!(monitor.should_poll());
    }

    #[test]
    fn test_monitor_event_serialization() {
        let event = MonitorEvent::NetworkConnected { latency_ms: 42 };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("NetworkConnected"));
        assert!(json.contains("42"));
    }

    #[test]
    fn test_monitor_event_portal() {
        let event = MonitorEvent::PortalDetected {
            redirect_url: Some("http://portal.example.com".to_string()),
        };
        let json = serde_json::to_string(&event).unwrap();
        assert!(json.contains("PortalDetected"));
        assert!(json.contains("portal.example.com"));
    }
}

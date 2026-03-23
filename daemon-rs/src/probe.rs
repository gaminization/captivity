//! Connectivity probe for captive portal detection.
//!
//! Sends lightweight HTTP requests to detect captive portals:
//! - HTTP 204 → Internet available
//! - HTTP redirect/other → Captive portal detected
//! - Connection error → Network unavailable

use serde::{Deserialize, Serialize};
use std::time::Duration;

/// Result of a connectivity probe.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ConnectivityStatus {
    Connected,
    PortalDetected,
    NetworkUnavailable,
}

/// Probe result with optional redirect URL.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProbeResult {
    pub status: ConnectivityStatus,
    pub redirect_url: Option<String>,
    pub latency_ms: u64,
}

/// Configuration for connectivity probes.
#[derive(Debug, Clone)]
pub struct ProbeConfig {
    pub url: String,
    pub timeout_ms: u64,
    pub user_agent: String,
}

impl Default for ProbeConfig {
    fn default() -> Self {
        Self {
            url: "https://clients3.google.com/generate_204".to_string(),
            timeout_ms: 5000,
            user_agent: "CaptivityDaemon/2.0".to_string(),
        }
    }
}

/// Probe internet connectivity via HTTP.
///
/// Sends a lightweight GET request and interprets the response
/// to determine if the device has internet access or is behind
/// a captive portal.
pub fn probe_connectivity(config: &ProbeConfig) -> ProbeResult {
    let start = std::time::Instant::now();

    let agent = ureq::AgentBuilder::new()
        .timeout(Duration::from_millis(config.timeout_ms))
        .redirects(0)
        .user_agent(&config.user_agent)
        .build();

    match agent.get(&config.url).call() {
        Ok(response) => {
            let latency = start.elapsed().as_millis() as u64;
            let status_code = response.status();

            if status_code == 204 {
                ProbeResult {
                    status: ConnectivityStatus::Connected,
                    redirect_url: None,
                    latency_ms: latency,
                }
            } else if [301, 302, 303, 307, 308].contains(&status_code) {
                let redirect = response
                    .header("Location")
                    .map(|s| s.to_string());
                ProbeResult {
                    status: ConnectivityStatus::PortalDetected,
                    redirect_url: redirect,
                    latency_ms: latency,
                }
            } else {
                // Non-204 response (e.g., 200 with HTML) → portal
                ProbeResult {
                    status: ConnectivityStatus::PortalDetected,
                    redirect_url: None,
                    latency_ms: latency,
                }
            }
        }
        Err(ureq::Error::Status(code, response)) => {
            let latency = start.elapsed().as_millis() as u64;
            if [301, 302, 303, 307, 308].contains(&code) {
                let redirect = response
                    .header("Location")
                    .map(|s| s.to_string());
                ProbeResult {
                    status: ConnectivityStatus::PortalDetected,
                    redirect_url: redirect,
                    latency_ms: latency,
                }
            } else {
                ProbeResult {
                    status: ConnectivityStatus::PortalDetected,
                    redirect_url: None,
                    latency_ms: latency,
                }
            }
        }
        Err(_) => {
            let latency = start.elapsed().as_millis() as u64;
            ProbeResult {
                status: ConnectivityStatus::NetworkUnavailable,
                redirect_url: None,
                latency_ms: latency,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_probe_config_defaults() {
        let config = ProbeConfig::default();
        assert!(config.url.contains("generate_204"));
        assert_eq!(config.timeout_ms, 5000);
    }

    #[test]
    fn test_connectivity_status_serialization() {
        let json = serde_json::to_string(&ConnectivityStatus::Connected).unwrap();
        assert_eq!(json, "\"connected\"");

        let json = serde_json::to_string(&ConnectivityStatus::PortalDetected).unwrap();
        assert_eq!(json, "\"portal_detected\"");
    }

    #[test]
    fn test_probe_result_serialization() {
        let result = ProbeResult {
            status: ConnectivityStatus::Connected,
            redirect_url: None,
            latency_ms: 42,
        };
        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("\"connected\""));
        assert!(json.contains("42"));
    }
}

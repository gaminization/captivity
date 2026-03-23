"""
Layered configuration system for Captivity.

Configuration sources (highest priority wins):
    1. Environment variables (CAPTIVITY_<SECTION>_<KEY>)
    2. User config file (~/.config/captivity/config.toml)
    3. Built-in defaults

Provides:
    - CaptivityConfig: main config class with typed access
    - get_config(): singleton accessor
    - DEFAULTS: built-in default values

Config file uses TOML format (parsed with stdlib tomllib on 3.11+,
or a minimal fallback parser for earlier versions).
"""

import os
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Any, Optional

from captivity.utils.logging import get_logger

logger = get_logger("config")

# --- Default config path ---


def _config_dir() -> Path:
    """Get XDG config directory for Captivity."""
    base = os.environ.get(
        "XDG_CONFIG_HOME", os.path.expanduser("~/.config"),
    )
    return Path(base) / "captivity"


def _config_path() -> Path:
    """Get default config file path."""
    return _config_dir() / "config.toml"


# --- Typed config sections ---


@dataclass
class ProbeConfig:
    """Connectivity probe settings."""
    url: str = "https://clients3.google.com/generate_204"
    timeout: float = 5.0
    interval: float = 30.0
    user_agent: str = "CaptivityProbe/1.0"


@dataclass
class DaemonConfig:
    """Daemon and service settings."""
    poll_interval: float = 30.0
    retry_base_delay: float = 5.0
    retry_max_delay: float = 300.0
    max_retries: int = 10
    log_level: str = "INFO"


@dataclass
class DashboardConfig:
    """Web dashboard settings."""
    host: str = "127.0.0.1"
    port: int = 8787
    enabled: bool = True


@dataclass
class SimulatorConfig:
    """Portal simulator settings."""
    host: str = "127.0.0.1"
    port: int = 9090
    default_scenario: str = "simple"


@dataclass
class PluginsConfig:
    """Plugin system settings."""
    auto_discover: bool = True
    marketplace_enabled: bool = True
    install_timeout: int = 120


@dataclass
class TelemetryConfig:
    """Telemetry and monitoring settings."""
    enabled: bool = True
    bandwidth_tracking: bool = True
    history_limit: int = 1000


@dataclass
class TrayConfig:
    """System tray UI settings."""
    enabled: bool = True
    notifications: bool = True
    icon_theme: str = "default"


@dataclass
class LoginConfig:
    """Login behavior settings."""
    auto_login: bool = True
    timeout: float = 10.0
    max_attempts: int = 5
    cache_endpoints: bool = True


# --- Main config ---


@dataclass
class CaptivityConfig:
    """Main configuration container.

    Access sections as attributes:
        config.probe.url
        config.daemon.poll_interval
        config.dashboard.port
    """
    probe: ProbeConfig = field(default_factory=ProbeConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    simulator: SimulatorConfig = field(default_factory=SimulatorConfig)
    plugins: PluginsConfig = field(default_factory=PluginsConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    tray: TrayConfig = field(default_factory=TrayConfig)
    login: LoginConfig = field(default_factory=LoginConfig)

    def get(self, section: str, key: str) -> Any:
        """Get a config value by section and key.

        Args:
            section: Config section name (e.g. 'probe').
            key: Key within the section (e.g. 'url').

        Returns:
            The config value.

        Raises:
            KeyError: If section or key does not exist.
        """
        sec = getattr(self, section, None)
        if sec is None:
            raise KeyError(f"Unknown config section: {section}")
        if not hasattr(sec, key):
            raise KeyError(f"Unknown config key: {section}.{key}")
        return getattr(sec, key)

    def set(self, section: str, key: str, value: Any) -> None:
        """Set a config value by section and key.

        Args:
            section: Config section name.
            key: Key within the section.
            value: New value (auto-coerced to field type).

        Raises:
            KeyError: If section or key does not exist.
        """
        sec = getattr(self, section, None)
        if sec is None:
            raise KeyError(f"Unknown config section: {section}")
        if not hasattr(sec, key):
            raise KeyError(f"Unknown config key: {section}.{key}")

        # Auto-coerce to match existing value type
        current = getattr(sec, key)
        value = _coerce(value, type(current))

        setattr(sec, key, value)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Export full config as nested dict."""
        result = {}
        for f in fields(self):
            result[f.name] = asdict(getattr(self, f.name))
        return result

    def sections(self) -> list[str]:
        """List all config section names."""
        return [f.name for f in fields(self)]

    def keys(self, section: str) -> list[str]:
        """List keys in a section."""
        sec = getattr(self, section, None)
        if sec is None:
            raise KeyError(f"Unknown config section: {section}")
        return [f.name for f in fields(sec)]


# --- Type coercion ---


def _coerce(value: Any, target_type: Any) -> Any:
    """Coerce a value to the target type.

    Args:
        value: Value to coerce.
        target_type: Target type (e.g. int, float, bool, str).
    """
    if isinstance(value, str):
        if target_type is bool or target_type == "bool":
            return value.lower() in ("true", "1", "yes", "on")
        if target_type is int or target_type == "int":
            return int(value)
        if target_type is float or target_type == "float":
            return float(value)
    return value


# --- TOML parsing ---


def _parse_toml(text: str) -> dict[str, dict[str, Any]]:
    """Parse TOML text into nested dict.

    Tries stdlib tomllib first (Python 3.11+), falls back to
    a minimal parser for simple key = value under [section].
    """
    try:
        import tomllib
        return tomllib.loads(text)
    except ImportError:
        pass

    # Minimal fallback parser
    result: dict[str, dict[str, Any]] = {}
    current_section = None

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            result.setdefault(current_section, {})
            continue
        if "=" in line and current_section:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # Parse value type
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            elif val.lower() in ("true", "false"):
                val = val.lower() == "true"
            elif "." in val:
                try:
                    val = float(val)
                except ValueError:
                    pass
            else:
                try:
                    val = int(val)
                except ValueError:
                    pass
            result[current_section][key] = val

    return result


def _to_toml(config: CaptivityConfig) -> str:
    """Serialize config to TOML format."""
    lines = ["# Captivity configuration file", ""]
    for section_name in config.sections():
        sec = getattr(config, section_name)
        lines.append(f"[{section_name}]")
        for f in fields(sec):
            val = getattr(sec, f.name)
            if isinstance(val, str):
                lines.append(f'{f.name} = "{val}"')
            elif isinstance(val, bool):
                lines.append(f"{f.name} = {str(val).lower()}")
            else:
                lines.append(f"{f.name} = {val}")
        lines.append("")
    return "\n".join(lines)


# --- Loading ---


def load_config(path: Optional[Path] = None) -> CaptivityConfig:
    """Load configuration with layered overrides.

    Priority (highest wins):
        1. Environment variables: CAPTIVITY_<SECTION>_<KEY>
        2. Config file (TOML)
        3. Built-in defaults

    Args:
        path: Optional config file path. Defaults to
              ~/.config/captivity/config.toml.

    Returns:
        Fully resolved CaptivityConfig instance.
    """
    config = CaptivityConfig()

    # Layer 1: File overrides
    config_path = path or _config_path()
    if config_path.exists():
        try:
            text = config_path.read_text()
            data = _parse_toml(text)
            for section, values in data.items():
                if hasattr(config, section):
                    for key, val in values.items():
                        try:
                            config.set(section, key, val)
                        except KeyError:
                            logger.warning(
                                "Unknown config: %s.%s", section, key,
                            )
            logger.info("Loaded config from %s", config_path)
        except Exception as exc:
            logger.warning("Failed to load config file: %s", exc)

    # Layer 2: Environment variable overrides
    prefix = "CAPTIVITY_"
    for section in config.sections():
        for key in config.keys(section):
            env_key = f"{prefix}{section.upper()}_{key.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is not None:
                try:
                    config.set(section, key, env_val)
                    logger.debug(
                        "Config override from env: %s=%s", env_key, env_val,
                    )
                except (KeyError, ValueError) as exc:
                    logger.warning("Bad env config %s: %s", env_key, exc)

    return config


def save_config(config: CaptivityConfig, path: Optional[Path] = None) -> None:
    """Save configuration to TOML file.

    Args:
        config: Config to save.
        path: Output path. Defaults to ~/.config/captivity/config.toml.
    """
    config_path = path or _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(_to_toml(config))
    logger.info("Saved config to %s", config_path)


def generate_default_config(path: Optional[Path] = None) -> Path:
    """Generate a default config file.

    Args:
        path: Output path.

    Returns:
        Path to the generated file.
    """
    config_path = path or _config_path()
    save_config(CaptivityConfig(), config_path)
    return config_path


# --- Singleton ---

_instance: Optional[CaptivityConfig] = None


def get_config(path: Optional[Path] = None) -> CaptivityConfig:
    """Get the global config singleton.

    Loads on first call, returns cached instance after.

    Args:
        path: Optional config file path for initial load.

    Returns:
        Global CaptivityConfig instance.
    """
    global _instance
    if _instance is None:
        _instance = load_config(path)
    return _instance


def reset_config() -> None:
    """Reset the global config singleton (mainly for tests)."""
    global _instance
    _instance = None

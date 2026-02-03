"""
Configuration loader utility for Apache Airflow ETL Demo Platform.

Loads and validates configuration from environment variables and files.
"""

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """
    Configuration loader with environment variable support and validation.

    Loads configuration from .env files and environment variables with
    type conversion and default values.
    """

    def __init__(self, env_file: str | None = None) -> None:
        """
        Initialize configuration loader.

        Args:
            env_file: Path to .env file (default: searches for .env in current dir)
        """
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        logger.debug("Configuration loader initialized")

    def get_str(self, key: str, default: str | None = None, required: bool = False) -> str:
        """
        Get string configuration value.

        Args:
            key: Environment variable name
            default: Default value if not found
            required: Raise error if not found and no default

        Returns:
            Configuration value as string

        Raises:
            ValueError: If required and not found
        """
        value = os.getenv(key, default)
        if required and value is None:
            msg = f"Required configuration key not found: {key}"
            logger.error(msg)
            raise ValueError(msg)
        return value if value is not None else (default or "")

    def get_int(self, key: str, default: int | None = None, required: bool = False) -> int:
        """
        Get integer configuration value.

        Args:
            key: Environment variable name
            default: Default value if not found
            required: Raise error if not found and no default

        Returns:
            Configuration value as integer

        Raises:
            ValueError: If required and not found, or if value cannot be converted
        """
        value = os.getenv(key)
        if value is None:
            if required:
                msg = f"Required configuration key not found: {key}"
                logger.error(msg)
                raise ValueError(msg)
            return default or 0

        try:
            return int(value)
        except ValueError as e:
            msg = f"Cannot convert {key}={value} to integer"
            logger.error(msg)
            raise ValueError(msg) from e

    def get_bool(self, key: str, default: bool = False, required: bool = False) -> bool:
        """
        Get boolean configuration value.

        Accepts: true/false, yes/no, 1/0 (case insensitive)

        Args:
            key: Environment variable name
            default: Default value if not found
            required: Raise error if not found and no default

        Returns:
            Configuration value as boolean

        Raises:
            ValueError: If required and not found
        """
        value = os.getenv(key)
        if value is None:
            if required:
                msg = f"Required configuration key not found: {key}"
                logger.error(msg)
                raise ValueError(msg)
            return default

        return value.lower() in ("true", "yes", "1", "on")

    def get_json(self, key: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Get JSON configuration value.

        Args:
            key: Environment variable name
            default: Default value if not found

        Returns:
            Configuration value as parsed JSON dict

        Raises:
            ValueError: If value is not valid JSON
        """
        value = os.getenv(key)
        if value is None:
            return default or {}

        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            msg = f"Cannot parse {key} as JSON: {value}"
            logger.error(msg)
            raise ValueError(msg) from e

    def load_warehouse_config(self) -> dict[str, Any]:
        """
        Load warehouse database configuration.

        Returns:
            Dict with host, port, database, user, password keys
        """
        config = {
            "host": self.get_str("WAREHOUSE_HOST", "airflow-warehouse", required=True),
            "port": self.get_int("WAREHOUSE_PORT", 5432),
            "database": self.get_str("WAREHOUSE_DB", "warehouse", required=True),
            "user": self.get_str("WAREHOUSE_USER", "warehouse_user", required=True),
            "password": self.get_str("WAREHOUSE_PASSWORD", "warehouse_pass", required=True),
        }
        logger.info("Warehouse configuration loaded", host=config["host"], database=config["database"])
        return config

    def load_smtp_config(self) -> dict[str, Any] | None:
        """
        Load SMTP configuration for email notifications.

        Returns:
            Dict with SMTP settings, or None if not configured
        """
        host = self.get_str("SMTP_HOST")
        if not host:
            logger.debug("SMTP not configured")
            return None

        config = {
            "host": host,
            "port": self.get_int("SMTP_PORT", 587),
            "user": self.get_str("SMTP_USER"),
            "password": self.get_str("SMTP_PASSWORD"),
            "from_email": self.get_str("SMTP_FROM", "airflow@example.com"),
            "use_tls": self.get_bool("SMTP_USE_TLS", True),
        }
        logger.info("SMTP configuration loaded", host=config["host"])
        return config

    def load_teams_config(self) -> str | None:
        """
        Load Microsoft Teams webhook URL.

        Returns:
            Teams webhook URL, or None if not configured
        """
        webhook_url = self.get_str("TEAMS_WEBHOOK_URL")
        if webhook_url:
            logger.info("Teams webhook configured")
        return webhook_url

    def load_telegram_config(self) -> dict[str, str] | None:
        """
        Load Telegram bot configuration.

        Returns:
            Dict with bot_token and chat_id, or None if not configured
        """
        bot_token = self.get_str("TELEGRAM_BOT_TOKEN")
        chat_id = self.get_str("TELEGRAM_CHAT_ID")

        if not bot_token or not chat_id:
            logger.debug("Telegram not configured")
            return None

        logger.info("Telegram configuration loaded")
        return {"bot_token": bot_token, "chat_id": chat_id}

    def load_dag_config_from_file(self, config_path: str) -> dict[str, Any]:
        """
        Load DAG configuration from JSON file.

        Args:
            config_path: Path to JSON configuration file

        Returns:
            Parsed DAG configuration dict

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is not valid JSON
        """
        path = Path(config_path)
        if not path.exists():
            msg = f"DAG config file not found: {config_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        try:
            with path.open("r") as f:
                config = json.load(f)
            logger.info("DAG configuration loaded", config_file=config_path)
            return config
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON in config file: {config_path}"
            logger.error(msg)
            raise ValueError(msg) from e


# Global config loader instance
_config_loader: ConfigLoader | None = None


def get_config_loader() -> ConfigLoader:
    """
    Get or create global ConfigLoader instance.

    Returns:
        Singleton ConfigLoader instance

    Example:
        >>> config = get_config_loader()
        >>> warehouse_config = config.load_warehouse_config()
        >>> db_host = warehouse_config["host"]
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader

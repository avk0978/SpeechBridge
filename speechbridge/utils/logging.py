"""
SpeechBridge Logging System
============================

Rotating log system with overwrite on each run:
- Current log: Overwrites on each run
- Archive log: Appends all runs with timestamps
- UTF-8 encoding for multilingual support
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class SpeechBridgeLogger:
    """
    Rotating logger with current and archive logs

    Features:
    - Current log overwrites on each run
    - Archive log keeps history of all runs
    - UTF-8 encoding for Russian/multilingual text
    - Automatic directory creation
    """

    DEFAULT_FORMAT = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
    DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(
        self,
        log_dir: str = "logs",
        log_level: int = logging.DEBUG,
        console_output: bool = True
    ):
        """
        Initialize logger system

        Args:
            log_dir: Directory for log files (default: "logs")
            log_level: Logging level (default: DEBUG)
            console_output: Whether to output to console (default: True)
        """
        self.log_dir = Path(log_dir)
        self.log_level = log_level
        self.console_output = console_output

        # Create log directory
        self.log_dir.mkdir(exist_ok=True, parents=True)

        # Define log files
        self.current_log = self.log_dir / "speechbridge_current.log"
        self.archive_log = self.log_dir / "speechbridge_archive.log"

        # Setup logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """
        Configure logging handlers

        Creates:
        - Current log handler (mode='w' - overwrite)
        - Archive log handler (mode='a' - append)
        - Console handler (optional)
        """
        # Create formatter
        formatter = logging.Formatter(
            self.DEFAULT_FORMAT,
            datefmt=self.DEFAULT_DATE_FORMAT
        )

        # Get root logger
        root_logger = logging.getLogger('speechbridge')
        root_logger.setLevel(self.log_level)

        # Remove existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # Current log handler (overwrite mode)
        current_handler = logging.FileHandler(
            self.current_log,
            mode='w',  # Overwrite on each run
            encoding='utf-8'
        )
        current_handler.setLevel(self.log_level)
        current_handler.setFormatter(formatter)
        root_logger.addHandler(current_handler)

        # Archive log handler (append mode)
        archive_handler = logging.FileHandler(
            self.archive_log,
            mode='a',  # Append to archive
            encoding='utf-8'
        )
        archive_handler.setLevel(self.log_level)
        archive_handler.setFormatter(formatter)
        root_logger.addHandler(archive_handler)

        # Console handler (optional)
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)  # Less verbose for console
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # Log session start in archive
        separator = "=" * 80
        root_logger.info(separator)
        root_logger.info(f"SpeechBridge session started at {datetime.now()}")
        root_logger.info(f"Log directory: {self.log_dir.absolute()}")
        root_logger.info(separator)

    def get_logger(self, name: str = 'speechbridge') -> logging.Logger:
        """
        Get logger instance

        Args:
            name: Logger name (default: 'speechbridge')

        Returns:
            logging.Logger: Configured logger
        """
        # Ensure logger is child of speechbridge namespace
        if not name.startswith('speechbridge'):
            name = f'speechbridge.{name}'
        return logging.getLogger(name)

    def get_current_log_path(self) -> Path:
        """
        Get path to current log file

        Returns:
            Path: Current log file path
        """
        return self.current_log

    def get_archive_log_path(self) -> Path:
        """
        Get path to archive log file

        Returns:
            Path: Archive log file path
        """
        return self.archive_log

    def read_current_log(self) -> str:
        """
        Read contents of current log

        Returns:
            str: Log contents
        """
        if self.current_log.exists():
            return self.current_log.read_text(encoding='utf-8')
        return ""

    def read_archive_log(self, lines: Optional[int] = None) -> str:
        """
        Read archive log contents

        Args:
            lines: Number of last lines to read (None = all)

        Returns:
            str: Log contents
        """
        if not self.archive_log.exists():
            return ""

        if lines is None:
            return self.archive_log.read_text(encoding='utf-8')

        # Read last N lines
        with open(self.archive_log, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return ''.join(all_lines[-lines:])

    def clear_archive(self) -> None:
        """
        Clear archive log file

        Warning: This deletes all archived logs!
        """
        if self.archive_log.exists():
            self.archive_log.unlink()
            logger = self.get_logger()
            logger.info("Archive log cleared")


def setup_logging(
    log_dir: str = "logs",
    log_level: int = logging.DEBUG,
    console_output: bool = True
) -> SpeechBridgeLogger:
    """
    Quick setup for logging system

    Args:
        log_dir: Directory for log files
        log_level: Logging level
        console_output: Enable console output

    Returns:
        SpeechBridgeLogger: Configured logger instance

    Example:
        >>> logger_system = setup_logging()
        >>> logger = logger_system.get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return SpeechBridgeLogger(
        log_dir=log_dir,
        log_level=log_level,
        console_output=console_output
    )

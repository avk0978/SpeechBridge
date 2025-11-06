"""
SpeechBridge Base Classes
==========================

Basic abstract classes for all SpeechBridge components.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

from .types import DeviceType
from .gpu import GPUManager


class BaseComponent(ABC):
    """Basic class for all SpeechBridge components"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: Component configuration
        """
        self.config = config or {}
        self.gpu_manager = GPUManager()
        self.device = self._get_device()
        self.logger = self._setup_logger()
        self._initialized = False

    def _get_device(self) -> DeviceType:
        """Definition of a processing device"""
        if self.config.get('use_gpu', True):
            return self.gpu_manager.get_optimal_device()
        return 'cpu'

    def _setup_logger(self) -> logging.Logger:
        """Configuring the logger for a component"""
        logger_name = f"speechbridge.{self.__class__.__name__.lower()}"
        return logging.getLogger(logger_name)

    @abstractmethod
    def initialize(self) -> None:
        """Component initialization"""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Configuration validation"""
        pass

    def is_initialized(self) -> bool:
        """Initialization verification"""
        return self._initialized

    def get_info(self) -> Dict[str, Any]:
        """Getting info on a component"""
        return {
            'name': self.__class__.__name__,
            'device': self.device,
            'initialized': self._initialized,
            'config': self.config
        }


class BaseProcessor(BaseComponent):
    """Base class for processors (ASR, Translation, TTS)"""

    @abstractmethod
    def process(self, input_data: Any) -> Any:
        """Input data processing"""
        pass

    def preprocess(self, input_data: Any) -> Any:
        """Data preprocessing"""
        return input_data

    def postprocess(self, output_data: Any) -> Any:
        """Data post-processing"""
        return output_data

"""
SpeechBridge GPU Management
============================
Automatic detection and management of GPUs for processing.
Support:

- NVIDIA CUDA (через PyTorch)
- Apple Silicon MPS (M1/M2/M3)
- CPU fallback
"""

from typing import Optional, Dict, Any
import logging

from .types import GPUInfo, DeviceType
from .exceptions import GPUException

logger = logging.getLogger(__name__)


class GPUManager:
    """GPU manager for automatic detection and utilization"""

    _instance = None
    _gpu_info: Optional[GPUInfo] = None

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Init GPU manager"""
        if self._gpu_info is None:
            self._gpu_info = self._detect_gpu()

    def _detect_gpu(self) -> GPUInfo:
        """
        Identifying available GPU devices

        Returns:
            GPUInfo: Information about GPU
        """
        gpu_info: GPUInfo = {
            'cuda_available': False,
            'cuda_devices': 0,
            'cuda_device_name': None,
            'mps_available': False,
            'tensorflow_gpu': 0,
            'optimal_device': 'cpu'
        }

        # Check CUDA (NVIDIA)
        try:
            import torch
            gpu_info['cuda_available'] = torch.cuda.is_available()
            if gpu_info['cuda_available']:
                gpu_info['cuda_devices'] = torch.cuda.device_count()
                gpu_info['cuda_device_name'] = torch.cuda.get_device_name(0)
                logger.info(f"CUDA detected: {gpu_info['cuda_device_name']}")
        except ImportError:
            logger.warning("PyTorch not installed, CUDA support disabled")
        except Exception as e:
            logger.error(f"Error detecting CUDA: {e}")

        # Check MPS (Apple Silicon)
        try:
            import torch
            if hasattr(torch.backends, 'mps'):
                gpu_info['mps_available'] = torch.backends.mps.is_available()
                if gpu_info['mps_available']:
                    logger.info("Apple MPS (Metal Performance Shaders) detected")
        except Exception as e:
            logger.error(f"Error detecting MPS: {e}")

        # Check TensorFlow GPU
        try:
            import tensorflow as tf
            gpu_devices = tf.config.list_physical_devices('GPU')
            gpu_info['tensorflow_gpu'] = len(gpu_devices)
            if gpu_devices:
                logger.info(f"TensorFlow GPU devices: {len(gpu_devices)}")
        except ImportError:
            logger.debug("TensorFlow not installed")
        except Exception as e:
            logger.error(f"Error detecting TensorFlow GPU: {e}")

        # Determining the optimal device
        gpu_info['optimal_device'] = self._determine_optimal_device(gpu_info)

        return gpu_info

    def _determine_optimal_device(self, gpu_info: GPUInfo) -> DeviceType:
        """
        Determining the optimal device for processing

        Args:
            gpu_info: Information about GPU

        Returns:
            DeviceType: Optimal device
        """
        if gpu_info['cuda_available']:
            return 'cuda'
        elif gpu_info['mps_available']:
            return 'mps'
        return 'cpu'

    def get_gpu_info(self) -> GPUInfo:
        """
        Getting information about the GPU

        Returns:
            GPUInfo: Information about GPU
        """
        if self._gpu_info is None:
            self._gpu_info = self._detect_gpu()
        return self._gpu_info

    def get_optimal_device(self) -> DeviceType:
        """
        Getting the best device

        Returns:
            DeviceType: Best device ('cuda', 'mps', 'cpu')
        """
        info = self.get_gpu_info()
        return info['optimal_device']

    def is_gpu_available(self) -> bool:
        """
        GPU availability check

        Returns:
            bool: True if GPU availability
        """
        info = self.get_gpu_info()
        return info['cuda_available'] or info['mps_available']

    def get_device_name(self) -> str:
        """
        Getting the device name

        Returns:
            str: Device name
        """
        info = self.get_gpu_info()
        if info['cuda_available'] and info['cuda_device_name']:
            return info['cuda_device_name']
        elif info['mps_available']:
            return "Apple Metal Performance Shaders (MPS)"
        return "CPU"

    def set_device(self, device: DeviceType) -> None:
        """
        Installation device

        Args:
            device: Device for use

        Raises:
            GPUException: If the device is unavailable
        """
        info = self.get_gpu_info()

        if device == 'cuda' and not info['cuda_available']:
            raise GPUException("CUDA device requested but not available")

        if device == 'mps' and not info['mps_available']:
            raise GPUException("MPS device requested but not available")

        # Updating the optimal device
        if self._gpu_info:
            self._gpu_info['optimal_device'] = device

        logger.info(f"Device set to: {device}")

    def get_memory_info(self) -> Dict[str, Any]:
        """
        Getting info about GPU memory

        Returns:
            Dict: GPU memory information
        """
        info = self.get_gpu_info()
        memory_info = {}

        if info['cuda_available']:
            try:
                import torch
                memory_info['cuda_memory_allocated'] = torch.cuda.memory_allocated(0)
                memory_info['cuda_memory_reserved'] = torch.cuda.memory_reserved(0)
                memory_info['cuda_max_memory_allocated'] = torch.cuda.max_memory_allocated(0)
            except Exception as e:
                logger.error(f"Error getting CUDA memory info: {e}")

        return memory_info

    def clear_cache(self) -> None:
        """Clearing the GPU cache"""
        info = self.get_gpu_info()

        if info['cuda_available']:
            try:
                import torch
                torch.cuda.empty_cache()
                logger.info("CUDA cache cleared")
            except Exception as e:
                logger.error(f"Error clearing CUDA cache: {e}")

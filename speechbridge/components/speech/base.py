"""
Base Speech Recognition Component
==================================

Abstract base class for all speech recognition engines.
"""

from abc import abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

from speechbridge.core.base import BaseProcessor
from speechbridge.core.types import TranscriptionResult
from speechbridge.core.exceptions import ComponentException


class BaseSpeechRecognizer(BaseProcessor):
    """
    Base class for speech recognition engines

    All speech recognizers must implement the transcribe() method
    and support GPU acceleration when available.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize speech recognizer

        Args:
            config: Configuration dictionary with parameters:
                - use_gpu: Whether to use GPU if available (default: True)
                - language: Source language code (default: 'auto')
                - confidence_threshold: Minimum confidence score (default: 0.0)
        """
        super().__init__(config)
        self.language = self.config.get('language', 'auto')
        self.confidence_threshold = self.config.get('confidence_threshold', 0.0)

    def process(self, input_data: Any) -> TranscriptionResult:
        """
        Process audio input and return transcription

        Args:
            input_data: Audio file path or audio data

        Returns:
            TranscriptionResult: Transcription with metadata
        """
        # Validate input
        audio_path = self._validate_audio_input(input_data)

        # Preprocess audio if needed
        processed_audio = self.preprocess(audio_path)

        # Perform transcription
        result = self.transcribe(processed_audio)

        # Postprocess result
        final_result = self.postprocess(result)

        return final_result

    @abstractmethod
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """
        Transcribe audio file to text

        Args:
            audio_path: Path to audio file

        Returns:
            TranscriptionResult: Transcription result with metadata

        Raises:
            ComponentException: If transcription fails
        """
        pass

    def _validate_audio_input(self, input_data: Any) -> str:
        """
        Validate and convert input to audio file path

        Args:
            input_data: Audio input (path or data)

        Returns:
            str: Validated audio file path

        Raises:
            ComponentException: If input is invalid
        """
        if isinstance(input_data, (str, Path)):
            audio_path = Path(input_data)
            if not audio_path.exists():
                raise ComponentException(
                    f"Audio file not found: {audio_path}",
                    {'path': str(audio_path)}
                )
            return str(audio_path)

        raise ComponentException(
            "Invalid audio input type",
            {'type': type(input_data).__name__}
        )

    def validate_config(self) -> bool:
        """
        Validate recognizer configuration

        Returns:
            bool: True if configuration is valid
        """
        # Check confidence threshold
        threshold = self.config.get('confidence_threshold', 0.0)
        if not 0.0 <= threshold <= 1.0:
            self.logger.error(f"Invalid confidence threshold: {threshold}")
            return False

        return True

    def get_supported_languages(self) -> list:
        """
        Get list of supported languages

        Returns:
            list: List of language codes
        """
        return ['auto']  # Override in subclasses

    def get_info(self) -> Dict[str, Any]:
        """
        Get recognizer information

        Returns:
            Dict: Recognizer info including supported languages
        """
        info = super().get_info()
        info.update({
            'language': self.language,
            'confidence_threshold': self.confidence_threshold,
            'supported_languages': self.get_supported_languages(),
            'gpu_enabled': self.device != 'cpu'
        })
        return info

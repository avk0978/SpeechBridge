"""
Whisper Speech Recognition
===========================

OpenAI Whisper-based speech recognition with GPU acceleration.
"""

from typing import Dict, Any, Optional
from pathlib import Path

from .base import BaseSpeechRecognizer
from speechbridge.core.types import TranscriptionResult
from speechbridge.core.exceptions import ComponentException


class WhisperRecognizer(BaseSpeechRecognizer):
    """
    OpenAI Whisper speech recognizer

    Supports multiple model sizes and automatic GPU acceleration.
    Models: tiny, base, small, medium, large, large-v2, large-v3
    """

    SUPPORTED_MODELS = ['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3']

    SUPPORTED_LANGUAGES = [
        'auto', 'en', 'zh', 'de', 'es', 'ru', 'ko', 'fr', 'ja', 'pt', 'tr', 'pl',
        'ca', 'nl', 'ar', 'sv', 'it', 'id', 'hi', 'fi', 'vi', 'he', 'uk', 'el',
        'ms', 'cs', 'ro', 'da', 'hu', 'ta', 'no', 'th', 'ur', 'hr', 'bg', 'lt',
        'la', 'mi', 'ml', 'cy', 'sk', 'te', 'fa', 'lv', 'bn', 'sr', 'az', 'sl',
        'kn', 'et', 'mk', 'br', 'eu', 'is', 'hy', 'ne', 'mn', 'bs', 'kk', 'sq',
        'sw', 'gl', 'mr', 'pa', 'si', 'km', 'sn', 'yo', 'so', 'af', 'oc', 'ka',
        'be', 'tg', 'sd', 'gu', 'am', 'yi', 'lo', 'uz', 'fo', 'ht', 'ps', 'tk',
        'nn', 'mt', 'sa', 'lb', 'my', 'bo', 'tl', 'mg', 'as', 'tt', 'haw', 'ln',
        'ha', 'ba', 'jw', 'su'
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Whisper recognizer

        Args:
            config: Configuration with parameters:
                - model: Model size (default: 'base')
                - use_gpu: Use GPU if available (default: True)
                - language: Source language (default: 'auto')
                - task: 'transcribe' or 'translate' (default: 'transcribe')
        """
        super().__init__(config)

        self.model_name = self.config.get('model', 'base')
        self.task = self.config.get('task', 'transcribe')
        self.model = None

        # Validate model name
        if self.model_name not in self.SUPPORTED_MODELS:
            self.logger.warning(
                f"Unknown model '{self.model_name}', using 'base'"
            )
            self.model_name = 'base'

    def initialize(self) -> None:
        """
        Initialize Whisper model

        Loads the model onto the appropriate device (GPU/CPU)
        """
        if self._initialized:
            return

        try:
            import whisper

            self.logger.info(
                f"Loading Whisper model '{self.model_name}' on {self.device}"
            )

            # Try loading on specified device
            try:
                self.model = whisper.load_model(
                    self.model_name,
                    device=self.device
                )
                self._initialized = True
                self.logger.info(f"Whisper model loaded successfully on {self.device}")

            except Exception as device_error:
                # If MPS fails, fallback to CPU
                if self.device == 'mps':
                    self.logger.warning(f"MPS failed: {str(device_error)[:100]}...")
                    self.logger.info("Falling back to CPU for Whisper")
                    self.device = 'cpu'
                    self.model = whisper.load_model(
                        self.model_name,
                        device='cpu'
                    )
                    self._initialized = True
                    self.logger.info("Whisper model loaded successfully on CPU")
                else:
                    raise

        except ImportError:
            raise ComponentException(
                "Whisper library not installed",
                {'solution': 'pip install openai-whisper'}
            )
        except Exception as e:
            raise ComponentException(
                f"Failed to load Whisper model: {e}",
                {'model': self.model_name, 'device': self.device}
            )

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        """
        Transcribe audio using Whisper

        Args:
            audio_path: Path to audio file

        Returns:
            TranscriptionResult: Transcription with segments and metadata
        """
        # Ensure model is loaded
        if not self._initialized:
            self.initialize()

        try:
            self.logger.info(f"Transcribing: {audio_path}")

            # Prepare transcription options
            options = {
                'task': self.task,
                'verbose': False
            }

            # Set language if not auto-detect
            if self.language != 'auto':
                options['language'] = self.language

            # Perform transcription
            result = self.model.transcribe(audio_path, **options)

            # Extract text and metadata
            transcription: TranscriptionResult = {
                'text': result['text'].strip(),
                'language': result.get('language', self.language),
                'confidence': self._calculate_confidence(result),
                'segments': result.get('segments', []),
                'duration': self._get_audio_duration(result)
            }

            self.logger.info(
                f"Transcription complete: {len(transcription['text'])} chars"
            )

            return transcription

        except Exception as e:
            raise ComponentException(
                f"Whisper transcription failed: {e}",
                {'audio': audio_path, 'model': self.model_name}
            )

    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """
        Calculate average confidence from segments

        Args:
            result: Whisper result dictionary

        Returns:
            float: Average confidence score (0.0-1.0)
        """
        segments = result.get('segments', [])
        if not segments:
            return 1.0

        # Calculate average probability from segments
        total_prob = sum(
            seg.get('avg_logprob', 0.0) for seg in segments
        )
        avg_prob = total_prob / len(segments) if segments else 0.0

        # Convert log probability to confidence (approximation)
        confidence = max(0.0, min(1.0, (avg_prob + 1.0) / 1.0))

        return confidence

    def _get_audio_duration(self, result: Dict[str, Any]) -> float:
        """
        Extract audio duration from result

        Args:
            result: Whisper result dictionary

        Returns:
            float: Duration in seconds
        """
        segments = result.get('segments', [])
        if segments:
            return segments[-1].get('end', 0.0)
        return 0.0

    def validate_config(self) -> bool:
        """
        Validate Whisper configuration

        Returns:
            bool: True if configuration is valid
        """
        if not super().validate_config():
            return False

        # Validate model
        if self.model_name not in self.SUPPORTED_MODELS:
            self.logger.error(f"Unsupported model: {self.model_name}")
            return False

        # Validate language
        if self.language not in self.SUPPORTED_LANGUAGES:
            self.logger.warning(
                f"Language '{self.language}' may not be supported"
            )

        # Validate task
        if self.task not in ['transcribe', 'translate']:
            self.logger.error(f"Invalid task: {self.task}")
            return False

        return True

    def get_supported_languages(self) -> list:
        """
        Get list of supported languages

        Returns:
            list: List of 99+ language codes
        """
        return self.SUPPORTED_LANGUAGES

    def get_info(self) -> Dict[str, Any]:
        """
        Get Whisper recognizer information

        Returns:
            Dict: Complete info including model details
        """
        info = super().get_info()
        info.update({
            'model': self.model_name,
            'task': self.task,
            'num_supported_languages': len(self.SUPPORTED_LANGUAGES)
        })
        return info

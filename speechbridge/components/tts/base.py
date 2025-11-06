"""
Base Text-to-Speech Component
==============================

Abstract base class for all TTS engines.
"""

from typing import Dict, Any, List, Optional
from abc import abstractmethod
from pathlib import Path

from speechbridge.core.base import BaseProcessor
from speechbridge.core.types import TTSResult


class BaseTTS(BaseProcessor):
    """
    Base class for text-to-speech engines

    All TTS engines must implement the synthesize() method
    and provide voice information.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize TTS engine

        Args:
            config: Configuration dictionary with parameters:
                - voice: Voice name/ID (default: engine-specific)
                - language: Target language code (default: 'en')
                - rate: Speech rate multiplier (default: 1.0)
                - pitch: Pitch adjustment (default: 0)
                - volume: Volume level 0-100 (default: 100)
                - use_gpu: Use GPU if available (default: True)
        """
        super().__init__(config)

        self.voice = self.config.get('voice', self._get_default_voice())
        self.language = self.config.get('language', 'en')
        self.rate = self.config.get('rate', 1.0)
        self.pitch = self.config.get('pitch', 0)
        self.volume = self.config.get('volume', 100)

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize TTS engine

        Load models, authenticate API, etc.
        """
        pass

    @abstractmethod
    def synthesize(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        language: Optional[str] = None
    ) -> TTSResult:
        """
        Synthesize speech from text

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            voice: Voice name (overrides config)
            language: Language code (overrides config)

        Returns:
            TTSResult: Synthesis result with metadata
        """
        pass

    def synthesize_batch(
        self,
        texts: List[str],
        output_dir: str,
        voice: Optional[str] = None,
        language: Optional[str] = None
    ) -> List[TTSResult]:
        """
        Synthesize multiple texts

        Default implementation synthesizes one by one.
        Override for batch optimization.

        Args:
            texts: List of texts to synthesize
            output_dir: Directory to save audio files
            voice: Voice name (overrides config)
            language: Language code (overrides config)

        Returns:
            List[TTSResult]: List of synthesis results
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)

        results = []
        for i, text in enumerate(texts):
            file_path = output_path / f"speech_{i:04d}.wav"
            result = self.synthesize(text, str(file_path), voice, language)
            results.append(result)

        return results

    @abstractmethod
    def get_available_voices(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available voices

        Args:
            language: Filter by language (optional)

        Returns:
            List of voice info dictionaries
        """
        pass

    def _get_default_voice(self) -> str:
        """
        Get default voice for engine

        Override in subclass to provide engine-specific default

        Returns:
            str: Default voice name/ID
        """
        return 'default'

    def validate_voice(self, voice: str, language: Optional[str] = None) -> bool:
        """
        Validate if voice is available

        Args:
            voice: Voice name to check
            language: Language filter (optional)

        Returns:
            bool: True if voice is available
        """
        voices = self.get_available_voices(language)
        voice_names = [v.get('name', '') for v in voices]
        return voice in voice_names

    def validate_config(self) -> bool:
        """
        Validate TTS configuration

        Returns:
            bool: True if configuration is valid
        """
        # Validate rate
        if not (0.1 <= self.rate <= 3.0):
            self.logger.error(f"Rate must be between 0.1 and 3.0, got {self.rate}")
            return False

        # Validate volume
        if not (0 <= self.volume <= 100):
            self.logger.error(f"Volume must be between 0 and 100, got {self.volume}")
            return False

        # Validate pitch
        if not (-20 <= self.pitch <= 20):
            self.logger.warning(f"Pitch {self.pitch} may be out of normal range (-20 to 20)")

        return True

    def process(self, input_data: Any) -> Any:
        """
        Process input (required by BaseProcessor)

        Args:
            input_data: Dict with 'text' and 'output_path' keys

        Returns:
            TTSResult: Synthesis result
        """
        if isinstance(input_data, dict):
            text = input_data.get('text', '')
            output_path = input_data.get('output_path', 'output.wav')
            voice = input_data.get('voice')
            language = input_data.get('language')
            return self.synthesize(text, output_path, voice, language)
        else:
            raise ValueError("TTS requires dict input with 'text' and 'output_path'")

    def get_info(self) -> Dict[str, Any]:
        """
        Get TTS engine information

        Returns:
            Dict: Complete TTS info
        """
        info = super().get_info()
        info.update({
            'voice': self.voice,
            'language': self.language,
            'rate': self.rate,
            'pitch': self.pitch,
            'volume': self.volume,
            'available_voices': len(self.get_available_voices()) if self._initialized else 0
        })
        return info

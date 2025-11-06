"""
Base Translation Component
===========================

Abstract base class for all translation engines.
"""

from typing import Dict, Any, List, Optional
from abc import abstractmethod

from speechbridge.core.base import BaseProcessor
from speechbridge.core.types import TranslationResult


class BaseTranslator(BaseProcessor):
    """
    Base class for translation engines

    All translators must implement the translate() method
    and provide language support information.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize translator

        Args:
            config: Configuration dictionary with parameters:
                - source_lang: Source language code (default: 'auto')
                - target_lang: Target language code (required)
                - preserve_formatting: Keep text formatting (default: True)
                - use_gpu: Use GPU if available (default: True)
        """
        super().__init__(config)

        self.source_lang = self.config.get('source_lang', 'auto')
        self.target_lang = self.config.get('target_lang', 'en')
        self.preserve_formatting = self.config.get('preserve_formatting', True)

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize translation engine

        Load models, authenticate API, etc.
        """
        pass

    @abstractmethod
    def translate(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ) -> TranslationResult:
        """
        Translate text

        Args:
            text: Text to translate
            source_lang: Source language (overrides config)
            target_lang: Target language (overrides config)

        Returns:
            TranslationResult: Translation with metadata
        """
        pass

    def translate_batch(
        self,
        texts: List[str],
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ) -> List[TranslationResult]:
        """
        Translate multiple texts

        Default implementation translates one by one.
        Override for batch optimization.

        Args:
            texts: List of texts to translate
            source_lang: Source language (overrides config)
            target_lang: Target language (overrides config)

        Returns:
            List[TranslationResult]: List of translations
        """
        return [
            self.translate(text, source_lang, target_lang)
            for text in texts
        ]

    @abstractmethod
    def get_supported_languages(self) -> Dict[str, List[str]]:
        """
        Get supported languages

        Returns:
            Dict with 'source' and 'target' language lists
        """
        pass

    def detect_language(self, text: str) -> str:
        """
        Detect text language

        Default implementation returns 'auto'.
        Override for actual detection.

        Args:
            text: Text to analyze

        Returns:
            str: Detected language code
        """
        return 'auto'

    def validate_config(self) -> bool:
        """
        Validate translator configuration

        Returns:
            bool: True if configuration is valid
        """
        if not self.target_lang:
            self.logger.error("Target language is required")
            return False

        # Check if languages are supported
        supported = self.get_supported_languages()

        if self.source_lang != 'auto' and self.source_lang not in supported.get('source', []):
            self.logger.warning(
                f"Source language '{self.source_lang}' may not be supported"
            )

        if self.target_lang not in supported.get('target', []):
            self.logger.error(
                f"Target language '{self.target_lang}' is not supported"
            )
            return False

        return True

    def process(self, input_data: Any) -> Any:
        """
        Process input (required by BaseProcessor)

        Args:
            input_data: Text or dict with 'text' key

        Returns:
            TranslationResult: Translation result
        """
        if isinstance(input_data, dict):
            text = input_data.get('text', '')
            source = input_data.get('source_lang')
            target = input_data.get('target_lang')
            return self.translate(text, source, target)
        else:
            return self.translate(str(input_data))

    def get_info(self) -> Dict[str, Any]:
        """
        Get translator information

        Returns:
            Dict: Complete translator info
        """
        info = super().get_info()
        info.update({
            'source_lang': self.source_lang,
            'target_lang': self.target_lang,
            'preserve_formatting': self.preserve_formatting,
            'supported_languages': self.get_supported_languages()
        })
        return info

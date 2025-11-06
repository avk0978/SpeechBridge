"""
DeepL Translation
=================

Professional-quality translation using DeepL API.
"""

from typing import Dict, Any, List, Optional
import os

from .base import BaseTranslator
from speechbridge.core.types import TranslationResult
from speechbridge.core.exceptions import ComponentException


class DeepLTranslator(BaseTranslator):
    """
    DeepL translation engine

    Provides high-quality neural translation via DeepL API.
    Supports 31+ languages with various formality levels.
    """

    # DeepL supported languages (source)
    SOURCE_LANGUAGES = [
        'auto', 'bg', 'cs', 'da', 'de', 'el', 'en', 'es', 'et', 'fi', 'fr',
        'hu', 'id', 'it', 'ja', 'ko', 'lt', 'lv', 'nb', 'nl', 'pl', 'pt',
        'ro', 'ru', 'sk', 'sl', 'sv', 'tr', 'uk', 'zh'
    ]

    # DeepL target languages (may have variants like EN-US, EN-GB)
    TARGET_LANGUAGES = [
        'bg', 'cs', 'da', 'de', 'el', 'en', 'en-us', 'en-gb', 'es', 'et',
        'fi', 'fr', 'hu', 'id', 'it', 'ja', 'ko', 'lt', 'lv', 'nb', 'nl',
        'pl', 'pt', 'pt-br', 'pt-pt', 'ro', 'ru', 'sk', 'sl', 'sv', 'tr',
        'uk', 'zh'
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize DeepL translator

        Args:
            config: Configuration with parameters:
                - api_key: DeepL API key (or use DEEPL_API_KEY env var)
                - source_lang: Source language (default: 'auto')
                - target_lang: Target language (required)
                - formality: 'default', 'more', or 'less' (default: 'default')
                - preserve_formatting: Keep formatting (default: True)
        """
        super().__init__(config)

        self.api_key = self.config.get('api_key') or os.getenv('DEEPL_API_KEY')
        self.formality = self.config.get('formality', 'default')
        self.translator = None

    def initialize(self) -> None:
        """
        Initialize DeepL translator

        Validates API key and creates translator instance
        """
        if self._initialized:
            return

        if not self.api_key:
            raise ComponentException(
                "DeepL API key is required",
                {'solution': 'Set DEEPL_API_KEY env var or provide api_key in config'}
            )

        try:
            import deepl

            self.logger.info("Initializing DeepL translator")

            # Create translator instance
            self.translator = deepl.Translator(self.api_key)

            # Test API key by getting usage
            usage = self.translator.get_usage()
            self.logger.info(
                f"DeepL initialized: {usage.character.count}/{usage.character.limit} characters used"
            )

            self._initialized = True

        except ImportError:
            raise ComponentException(
                "DeepL library not installed",
                {'solution': 'pip install deepl'}
            )
        except Exception as e:
            raise ComponentException(
                f"Failed to initialize DeepL: {e}",
                {'api_key': 'Check if API key is valid'}
            )

    def translate(
        self,
        text: str,
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ) -> TranslationResult:
        """
        Translate text using DeepL

        Args:
            text: Text to translate
            source_lang: Source language (overrides config)
            target_lang: Target language (overrides config)

        Returns:
            TranslationResult: Translation with metadata
        """
        # Ensure translator is initialized
        if not self._initialized:
            self.initialize()

        # Use provided languages or fall back to config
        src_lang = source_lang or self.source_lang
        tgt_lang = target_lang or self.target_lang

        try:
            self.logger.info(f"Translating {src_lang} -> {tgt_lang}: {len(text)} chars")

            # Prepare translation options
            options = {
                'target_lang': tgt_lang.upper(),
                'preserve_formatting': self.preserve_formatting
            }

            # Set source language if not auto-detect
            if src_lang != 'auto':
                options['source_lang'] = src_lang.upper()

            # Set formality if supported
            if self.formality != 'default':
                options['formality'] = self.formality

            # Perform translation
            result = self.translator.translate_text(text, **options)

            # Build translation result
            translation: TranslationResult = {
                'text': result.text,
                'source_lang': result.detected_source_lang.lower() if hasattr(result, 'detected_source_lang') else src_lang,
                'target_lang': tgt_lang,
                'confidence': 1.0  # DeepL doesn't provide confidence scores
            }

            self.logger.info(
                f"Translation complete: {len(translation['text'])} chars"
            )

            return translation

        except Exception as e:
            raise ComponentException(
                f"DeepL translation failed: {e}",
                {'text_length': len(text), 'source': src_lang, 'target': tgt_lang}
            )

    def translate_batch(
        self,
        texts: List[str],
        source_lang: Optional[str] = None,
        target_lang: Optional[str] = None
    ) -> List[TranslationResult]:
        """
        Translate multiple texts in batch (more efficient)

        Args:
            texts: List of texts to translate
            source_lang: Source language (overrides config)
            target_lang: Target language (overrides config)

        Returns:
            List[TranslationResult]: List of translations
        """
        # Ensure translator is initialized
        if not self._initialized:
            self.initialize()

        # Use provided languages or fall back to config
        src_lang = source_lang or self.source_lang
        tgt_lang = target_lang or self.target_lang

        try:
            self.logger.info(f"Batch translating {len(texts)} texts")

            # Prepare translation options
            options = {
                'target_lang': tgt_lang.upper(),
                'preserve_formatting': self.preserve_formatting
            }

            if src_lang != 'auto':
                options['source_lang'] = src_lang.upper()

            if self.formality != 'default':
                options['formality'] = self.formality

            # Perform batch translation
            results = self.translator.translate_text(texts, **options)

            # Convert to TranslationResult list
            translations = []
            for result in results:
                translation: TranslationResult = {
                    'text': result.text,
                    'source_lang': result.detected_source_lang.lower() if hasattr(result, 'detected_source_lang') else src_lang,
                    'target_lang': tgt_lang,
                    'confidence': 1.0
                }
                translations.append(translation)

            self.logger.info(f"Batch translation complete: {len(translations)} results")

            return translations

        except Exception as e:
            raise ComponentException(
                f"DeepL batch translation failed: {e}",
                {'num_texts': len(texts), 'source': src_lang, 'target': tgt_lang}
            )

    def get_supported_languages(self) -> Dict[str, List[str]]:
        """
        Get supported languages

        Returns:
            Dict with 'source' and 'target' language lists
        """
        return {
            'source': self.SOURCE_LANGUAGES,
            'target': self.TARGET_LANGUAGES
        }

    def detect_language(self, text: str) -> str:
        """
        Detect language by performing auto-translation

        Args:
            text: Text to analyze

        Returns:
            str: Detected language code
        """
        if not self._initialized:
            self.initialize()

        try:
            # Translate with auto-detect to get source language
            result = self.translator.translate_text(
                text[:100],  # Use first 100 chars for detection
                target_lang=self.target_lang.upper()
            )

            if hasattr(result, 'detected_source_lang'):
                return result.detected_source_lang.lower()
            return 'auto'

        except Exception as e:
            self.logger.warning(f"Language detection failed: {e}")
            return 'auto'

    def get_usage(self) -> Dict[str, Any]:
        """
        Get API usage statistics

        Returns:
            Dict with usage information
        """
        if not self._initialized:
            self.initialize()

        try:
            usage = self.translator.get_usage()
            return {
                'character_count': usage.character.count,
                'character_limit': usage.character.limit,
                'usage_percent': (usage.character.count / usage.character.limit * 100) if usage.character.limit else 0
            }
        except Exception as e:
            self.logger.error(f"Failed to get usage: {e}")
            return {}

    def validate_config(self) -> bool:
        """
        Validate DeepL configuration

        Returns:
            bool: True if configuration is valid
        """
        if not super().validate_config():
            return False

        # Validate API key
        if not self.api_key:
            self.logger.error("API key is required")
            return False

        # Validate formality
        if self.formality not in ['default', 'more', 'less']:
            self.logger.error(f"Invalid formality: {self.formality}")
            return False

        return True

    def get_info(self) -> Dict[str, Any]:
        """
        Get DeepL translator information

        Returns:
            Dict: Complete translator info
        """
        info = super().get_info()
        info.update({
            'translator': 'DeepL',
            'formality': self.formality,
            'api_key_set': bool(self.api_key),
            'usage': self.get_usage() if self._initialized else {}
        })
        return info

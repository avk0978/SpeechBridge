"""
SpeechBridge Pipeline Builder
==============================

Builder pattern for easy pipeline construction.
"""

from typing import Dict, Any, Optional, Callable
from pathlib import Path

from .pipeline import VideoTranslationPipeline
from ..components.speech.base import BaseSpeechRecognizer
from ..components.speech.whisper import WhisperRecognizer
from ..components.translation.base import BaseTranslator
from ..components.translation.deepl import DeepLTranslator
from ..components.tts.base import BaseTTS
from ..components.tts.edge_tts import EdgeTTS
from ..components.video.base import BaseVideoProcessor
from ..components.video.processor import FFmpegProcessor


class PipelineBuilder:
    """
    Builder for VideoTranslationPipeline

    Provides fluent API for pipeline construction with sensible defaults.

    Example:
        >>> pipeline = (PipelineBuilder()
        ...     .with_whisper(model='base')
        ...     .with_deepl(api_key='...')
        ...     .with_edge_tts()
        ...     .with_ffmpeg()
        ...     .build())
    """

    def __init__(self):
        """Initialize builder"""
        self._speech_recognizer: Optional[BaseSpeechRecognizer] = None
        self._translator: Optional[BaseTranslator] = None
        self._tts_engine: Optional[BaseTTS] = None
        self._video_processor: Optional[BaseVideoProcessor] = None
        self._pipeline_config: Dict[str, Any] = {}

    # Speech Recognition Builders

    def with_speech_recognizer(
        self,
        recognizer: BaseSpeechRecognizer
    ) -> 'PipelineBuilder':
        """
        Set custom speech recognizer

        Args:
            recognizer: Custom speech recognizer instance

        Returns:
            PipelineBuilder: Self for chaining
        """
        self._speech_recognizer = recognizer
        return self

    def with_whisper(
        self,
        model: str = 'base',
        language: str = 'auto',
        **kwargs
    ) -> 'PipelineBuilder':
        """
        Use Whisper speech recognizer

        Args:
            model: Whisper model size (default: 'base')
            language: Source language (default: 'auto')
            **kwargs: Additional Whisper config

        Returns:
            PipelineBuilder: Self for chaining
        """
        config = {
            'model': model,
            'language': language,
            **kwargs
        }
        self._speech_recognizer = WhisperRecognizer(config)
        return self

    # Translation Builders

    def with_translator(
        self,
        translator: BaseTranslator
    ) -> 'PipelineBuilder':
        """
        Set custom translator

        Args:
            translator: Custom translator instance

        Returns:
            PipelineBuilder: Self for chaining
        """
        self._translator = translator
        return self

    def with_deepl(
        self,
        api_key: Optional[str] = None,
        source_lang: str = 'auto',
        target_lang: str = 'en',
        **kwargs
    ) -> 'PipelineBuilder':
        """
        Use DeepL translator

        Args:
            api_key: DeepL API key (or use DEEPL_API_KEY env var)
            source_lang: Source language (default: 'auto')
            target_lang: Target language (default: 'en')
            **kwargs: Additional DeepL config

        Returns:
            PipelineBuilder: Self for chaining
        """
        config = {
            'source_lang': source_lang,
            'target_lang': target_lang,
            **kwargs
        }
        if api_key:
            config['api_key'] = api_key

        self._translator = DeepLTranslator(config)
        return self

    # TTS Builders

    def with_tts(
        self,
        tts_engine: BaseTTS
    ) -> 'PipelineBuilder':
        """
        Set custom TTS engine

        Args:
            tts_engine: Custom TTS engine instance

        Returns:
            PipelineBuilder: Self for chaining
        """
        self._tts_engine = tts_engine
        return self

    def with_edge_tts(
        self,
        voice: str = 'en-US-AriaNeural',
        rate: float = 1.0,
        **kwargs
    ) -> 'PipelineBuilder':
        """
        Use Edge TTS engine

        Args:
            voice: Voice name (default: 'en-US-AriaNeural')
            rate: Speech rate (default: 1.0)
            **kwargs: Additional Edge TTS config

        Returns:
            PipelineBuilder: Self for chaining
        """
        config = {
            'voice': voice,
            'rate': rate,
            **kwargs
        }
        self._tts_engine = EdgeTTS(config)
        return self

    # Video Processor Builders

    def with_video_processor(
        self,
        processor: BaseVideoProcessor
    ) -> 'PipelineBuilder':
        """
        Set custom video processor

        Args:
            processor: Custom video processor instance

        Returns:
            PipelineBuilder: Self for chaining
        """
        self._video_processor = processor
        return self

    def with_ffmpeg(
        self,
        video_codec: str = 'libx264',
        audio_codec: str = 'aac',
        **kwargs
    ) -> 'PipelineBuilder':
        """
        Use FFmpeg video processor

        Args:
            video_codec: Video codec (default: 'libx264')
            audio_codec: Audio codec (default: 'aac')
            **kwargs: Additional FFmpeg config

        Returns:
            PipelineBuilder: Self for chaining
        """
        config = {
            'video_codec': video_codec,
            'audio_codec': audio_codec,
            **kwargs
        }
        self._video_processor = FFmpegProcessor(config)
        return self

    # Pipeline Configuration

    def with_config(
        self,
        temp_dir: str = 'temp',
        keep_temp: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> 'PipelineBuilder':
        """
        Set pipeline configuration

        Args:
            temp_dir: Temporary files directory (default: 'temp')
            keep_temp: Keep temporary files (default: False)
            progress_callback: Progress callback function

        Returns:
            PipelineBuilder: Self for chaining
        """
        self._pipeline_config = {
            'temp_dir': temp_dir,
            'keep_temp': keep_temp,
            'progress_callback': progress_callback
        }
        return self

    def with_temp_dir(self, temp_dir: str) -> 'PipelineBuilder':
        """
        Set temporary directory

        Args:
            temp_dir: Path to temp directory

        Returns:
            PipelineBuilder: Self for chaining
        """
        self._pipeline_config['temp_dir'] = temp_dir
        return self

    def with_progress_callback(
        self,
        callback: Callable[[int, str], None]
    ) -> 'PipelineBuilder':
        """
        Set progress callback

        Args:
            callback: Function(percent: int, message: str)

        Returns:
            PipelineBuilder: Self for chaining
        """
        self._pipeline_config['progress_callback'] = callback
        return self

    def keep_temporary_files(self, keep: bool = True) -> 'PipelineBuilder':
        """
        Configure temporary file retention

        Args:
            keep: Keep temporary files (default: True)

        Returns:
            PipelineBuilder: Self for chaining
        """
        self._pipeline_config['keep_temp'] = keep
        return self

    # Build Methods

    def build(self) -> VideoTranslationPipeline:
        """
        Build pipeline with configured components

        Returns:
            VideoTranslationPipeline: Configured pipeline

        Raises:
            ValueError: If required components are missing
        """
        # Validate components
        if not self._speech_recognizer:
            raise ValueError("Speech recognizer not configured. Use with_whisper() or with_speech_recognizer()")

        if not self._translator:
            raise ValueError("Translator not configured. Use with_deepl() or with_translator()")

        if not self._tts_engine:
            raise ValueError("TTS engine not configured. Use with_edge_tts() or with_tts()")

        if not self._video_processor:
            raise ValueError("Video processor not configured. Use with_ffmpeg() or with_video_processor()")

        # Create pipeline
        pipeline = VideoTranslationPipeline(
            speech_recognizer=self._speech_recognizer,
            translator=self._translator,
            tts_engine=self._tts_engine,
            video_processor=self._video_processor,
            config=self._pipeline_config
        )

        return pipeline

    def build_and_validate(self) -> VideoTranslationPipeline:
        """
        Build pipeline and validate all components

        Returns:
            VideoTranslationPipeline: Validated pipeline

        Raises:
            ValueError: If components are invalid
        """
        pipeline = self.build()

        if not pipeline.validate_components():
            raise ValueError("Pipeline validation failed. Check component configurations.")

        return pipeline

    # Preset Configurations

    @staticmethod
    def create_default() -> 'PipelineBuilder':
        """
        Create builder with default configuration

        Returns:
            PipelineBuilder: Configured builder
        """
        return (PipelineBuilder()
                .with_whisper(model='base')
                .with_edge_tts()
                .with_ffmpeg())

    @staticmethod
    def create_fast() -> 'PipelineBuilder':
        """
        Create builder optimized for speed

        Returns:
            PipelineBuilder: Fast configuration
        """
        return (PipelineBuilder()
                .with_whisper(model='tiny')
                .with_edge_tts(rate=1.2)
                .with_ffmpeg(video_codec='copy'))

    @staticmethod
    def create_quality() -> 'PipelineBuilder':
        """
        Create builder optimized for quality

        Returns:
            PipelineBuilder: Quality configuration
        """
        return (PipelineBuilder()
                .with_whisper(model='large-v3')
                .with_edge_tts(rate=1.0)
                .with_ffmpeg(video_codec='libx265', audio_codec='aac'))

    def __repr__(self) -> str:
        """String representation"""
        components = []
        if self._speech_recognizer:
            components.append(f"speech={self._speech_recognizer.__class__.__name__}")
        if self._translator:
            components.append(f"translator={self._translator.__class__.__name__}")
        if self._tts_engine:
            components.append(f"tts={self._tts_engine.__class__.__name__}")
        if self._video_processor:
            components.append(f"video={self._video_processor.__class__.__name__}")

        return f"PipelineBuilder({', '.join(components)})"


# Convenience function for quick pipeline creation
def create_pipeline(
    speech_model: str = 'base',
    target_language: str = 'en',
    deepl_api_key: Optional[str] = None,
    **kwargs
) -> VideoTranslationPipeline:
    """
    Quick pipeline creation with common settings

    Args:
        speech_model: Whisper model size (default: 'base')
        target_language: Target language for translation (default: 'en')
        deepl_api_key: DeepL API key (optional, uses env var if not provided)
        **kwargs: Additional pipeline config

    Returns:
        VideoTranslationPipeline: Configured pipeline

    Example:
        >>> pipeline = create_pipeline(
        ...     speech_model='base',
        ...     target_language='ru',
        ...     deepl_api_key='your-key'
        ... )
    """
    builder = (PipelineBuilder()
               .with_whisper(model=speech_model)
               .with_deepl(api_key=deepl_api_key, target_lang=target_language)
               .with_edge_tts()
               .with_ffmpeg())

    if kwargs:
        builder.with_config(**kwargs)

    return builder.build()

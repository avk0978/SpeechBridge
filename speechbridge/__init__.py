"""
SpeechBridge Framework
======================

Модульный фреймворк для автоматического перевода видео с поддержкой GPU.

Основные компоненты:
- Core: Базовые модули и GPU управление
- Components: Компоненты для ASR, Translation, TTS, Video
- Config: Система конфигурации
- Web: Flask Web UI
- CLI: Command-line interface

=============================================================================

A modular framework for automatic video translation with GPU support.

Main components:
- Core: Core modules and GPU management
- Components: Components for ASR, Translation, TTS, Video
- Config: Configuration system
- Web: Flask Web UI
- CLI: Command-line interface

==============================================================================

Example:
    >>> from speechbridge import SpeechBridgeBuilder
    >>> builder = SpeechBridgeBuilder()
    >>> translator = builder.build()
"""

from .__version__ import __version__, __author__, __license__, __description__

__all__ = [
    '__version__',
    '__author__',
    '__license__',
    '__description__',
]

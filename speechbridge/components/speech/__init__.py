"""
Speech Recognition Components
==============================

Automatic Speech Recognition (ASR) components with GPU support.

Available engines:
- WhisperRecognizer: OpenAI Whisper (local, GPU-accelerated)
- GoogleRecognizer: Google Cloud Speech-to-Text
- SphinxRecognizer: CMU Sphinx (offline)
"""

from .base import BaseSpeechRecognizer
from .whisper import WhisperRecognizer

__all__ = [
    'BaseSpeechRecognizer',
    'WhisperRecognizer',
]

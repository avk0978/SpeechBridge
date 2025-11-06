"""
SpeechBridge Type Definitions
==============================

TypedDict defenitions for type hints в SpeechBridge.
"""

from typing import TypedDict, Optional, Literal, Any, Dict, List
from typing_extensions import NotRequired


class GPUInfo(TypedDict):
    """Infomation about GPU"""
    cuda_available: bool
    cuda_devices: int
    cuda_device_name: Optional[str]
    mps_available: bool
    tensorflow_gpu: int
    optimal_device: Literal['cuda', 'mps', 'cpu']


class AudioConfig(TypedDict):
    """Audio config"""
    sample_rate: int
    channels: int
    format: str


class TranscriptionResult(TypedDict):
    """Transcription results"""
    text: str
    language: str
    confidence: float
    segments: NotRequired[List[Dict[str, Any]]]
    duration: NotRequired[float]


class TranslationResult(TypedDict):
    """Translation results"""
    text: str
    source_lang: str
    target_lang: str
    confidence: NotRequired[float]
    metadata: NotRequired[Dict[str, Any]]


class TTSResult(TypedDict):
    """Text-to-speech result"""
    audio_path: str
    duration: float
    voice: str
    language: str
    text_length: int


class VideoInfo(TypedDict):
    """Video file information"""
    path: str
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    bitrate: int
    size: int


class ProcessingResult(TypedDict):
    """Final processing result"""
    success: bool
    output_path: Optional[str]
    transcription: NotRequired[TranscriptionResult]
    translation: NotRequired[TranslationResult]
    tts: NotRequired[TTSResult]
    errors: NotRequired[List[str]]
    warnings: NotRequired[List[str]]
    metadata: NotRequired[Dict[str, Any]]


DeviceType = Literal['cuda', 'mps', 'cpu']
LogLevel = Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

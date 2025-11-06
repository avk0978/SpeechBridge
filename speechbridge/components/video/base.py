"""
Base Video Processor
====================

Abstract base class for video processing components.
"""

from typing import Dict, Any, Optional
from abc import abstractmethod
from pathlib import Path

from speechbridge.core.base import BaseProcessor
from speechbridge.core.types import VideoInfo


class BaseVideoProcessor(BaseProcessor):
    """
    Base class for video processors

    All video processors must implement video manipulation methods
    like extracting audio, merging audio, getting video info, etc.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize video processor

        Args:
            config: Configuration dictionary with parameters:
                - output_format: Video format (default: 'mp4')
                - video_codec: Video codec (default: 'libx264')
                - audio_codec: Audio codec (default: 'aac')
                - audio_bitrate: Audio bitrate (default: '128k')
                - use_gpu: Use GPU acceleration (default: True)
        """
        super().__init__(config)

        self.output_format = self.config.get('output_format', 'mp4')
        self.video_codec = self.config.get('video_codec', 'libx264')
        self.audio_codec = self.config.get('audio_codec', 'aac')
        self.audio_bitrate = self.config.get('audio_bitrate', '128k')

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize video processor

        Validate ffmpeg installation, check codecs, etc.
        """
        pass

    @abstractmethod
    def extract_audio(
        self,
        video_path: str,
        audio_path: str,
        audio_format: str = 'wav'
    ) -> Dict[str, Any]:
        """
        Extract audio from video

        Args:
            video_path: Path to input video
            audio_path: Path to save extracted audio
            audio_format: Audio format (default: 'wav')

        Returns:
            Dict with extraction info (duration, sample_rate, etc.)
        """
        pass

    @abstractmethod
    def merge_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        remove_original_audio: bool = True
    ) -> Dict[str, Any]:
        """
        Merge audio with video

        Args:
            video_path: Path to input video
            audio_path: Path to audio file
            output_path: Path to save output video
            remove_original_audio: Remove original audio (default: True)

        Returns:
            Dict with merge info
        """
        pass

    @abstractmethod
    def get_video_info(self, video_path: str) -> VideoInfo:
        """
        Get video file information

        Args:
            video_path: Path to video file

        Returns:
            VideoInfo: Video metadata
        """
        pass

    @abstractmethod
    def convert_video(
        self,
        input_path: str,
        output_path: str,
        video_codec: Optional[str] = None,
        audio_codec: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert video to different format/codec

        Args:
            input_path: Path to input video
            output_path: Path to output video
            video_codec: Video codec (overrides config)
            audio_codec: Audio codec (overrides config)

        Returns:
            Dict with conversion info
        """
        pass

    def validate_video_path(self, video_path: str) -> bool:
        """
        Validate if video file exists and is accessible

        Args:
            video_path: Path to video file

        Returns:
            bool: True if valid
        """
        path = Path(video_path)
        if not path.exists():
            self.logger.error(f"Video file not found: {video_path}")
            return False

        if not path.is_file():
            self.logger.error(f"Path is not a file: {video_path}")
            return False

        # Check file extension
        valid_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        if path.suffix.lower() not in valid_extensions:
            self.logger.warning(
                f"Unusual video extension: {path.suffix}"
            )

        return True

    def validate_audio_path(self, audio_path: str) -> bool:
        """
        Validate if audio file exists and is accessible

        Args:
            audio_path: Path to audio file

        Returns:
            bool: True if valid
        """
        path = Path(audio_path)
        if not path.exists():
            self.logger.error(f"Audio file not found: {audio_path}")
            return False

        if not path.is_file():
            self.logger.error(f"Path is not a file: {audio_path}")
            return False

        # Check file extension
        valid_extensions = ['.wav', '.mp3', '.aac', '.flac', '.ogg', '.m4a']
        if path.suffix.lower() not in valid_extensions:
            self.logger.warning(
                f"Unusual audio extension: {path.suffix}"
            )

        return True

    def validate_config(self) -> bool:
        """
        Validate video processor configuration

        Returns:
            bool: True if configuration is valid
        """
        # Validate video codec
        valid_video_codecs = [
            'libx264', 'libx265', 'h264_nvenc', 'hevc_nvenc',
            'h264_qsv', 'hevc_qsv', 'copy'
        ]
        if self.video_codec not in valid_video_codecs:
            self.logger.warning(
                f"Video codec '{self.video_codec}' may not be supported"
            )

        # Validate audio codec
        valid_audio_codecs = ['aac', 'mp3', 'libmp3lame', 'opus', 'vorbis', 'copy']
        if self.audio_codec not in valid_audio_codecs:
            self.logger.warning(
                f"Audio codec '{self.audio_codec}' may not be supported"
            )

        return True

    def process(self, input_data: Any) -> Any:
        """
        Process input (required by BaseProcessor)

        Args:
            input_data: Dict with operation parameters

        Returns:
            Result based on operation type
        """
        if not isinstance(input_data, dict):
            raise ValueError("Video processor requires dict input with operation type")

        operation = input_data.get('operation')

        if operation == 'extract_audio':
            return self.extract_audio(
                input_data['video_path'],
                input_data['audio_path'],
                input_data.get('audio_format', 'wav')
            )
        elif operation == 'merge_audio':
            return self.merge_audio(
                input_data['video_path'],
                input_data['audio_path'],
                input_data['output_path'],
                input_data.get('remove_original_audio', True)
            )
        elif operation == 'get_info':
            return self.get_video_info(input_data['video_path'])
        elif operation == 'convert':
            return self.convert_video(
                input_data['input_path'],
                input_data['output_path'],
                input_data.get('video_codec'),
                input_data.get('audio_codec')
            )
        else:
            raise ValueError(f"Unknown operation: {operation}")

    def get_info(self) -> Dict[str, Any]:
        """
        Get video processor information

        Returns:
            Dict: Complete processor info
        """
        info = super().get_info()
        info.update({
            'output_format': self.output_format,
            'video_codec': self.video_codec,
            'audio_codec': self.audio_codec,
            'audio_bitrate': self.audio_bitrate
        })
        return info

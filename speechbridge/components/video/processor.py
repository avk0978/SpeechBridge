"""
FFmpeg Video Processor
======================

Video processing using FFmpeg.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import subprocess
import json
import shutil

from .base import BaseVideoProcessor
from speechbridge.core.types import VideoInfo
from speechbridge.core.exceptions import ComponentException


class FFmpegProcessor(BaseVideoProcessor):
    """
    FFmpeg-based video processor

    Provides video manipulation using FFmpeg:
    - Extract audio from video
    - Merge audio with video
    - Get video information
    - Convert video formats
    - GPU acceleration support
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize FFmpeg processor

        Args:
            config: Configuration with standard video processor parameters
        """
        super().__init__(config)

        self.ffmpeg_path = None
        self.ffprobe_path = None

    def initialize(self) -> None:
        """
        Initialize FFmpeg processor

        Validates FFmpeg installation and checks codecs
        """
        if self._initialized:
            return

        try:
            # Check if ffmpeg is available
            self.ffmpeg_path = shutil.which('ffmpeg')
            if not self.ffmpeg_path:
                raise ComponentException(
                    "FFmpeg not found",
                    {'solution': 'Install FFmpeg: https://ffmpeg.org/download.html'}
                )

            # Check if ffprobe is available
            self.ffprobe_path = shutil.which('ffprobe')
            if not self.ffprobe_path:
                raise ComponentException(
                    "FFprobe not found",
                    {'solution': 'Install FFmpeg (includes ffprobe)'}
                )

            # Get FFmpeg version
            result = subprocess.run(
                [self.ffmpeg_path, '-version'],
                capture_output=True,
                text=True
            )
            version_line = result.stdout.split('\n')[0]

            self.logger.info(f"FFmpeg initialized: {version_line}")

            # Configure GPU acceleration if available
            if self.gpu_manager.is_gpu_available() and self.config.get('use_gpu', True):
                self._configure_gpu_acceleration()

            self._initialized = True

        except Exception as e:
            raise ComponentException(
                f"Failed to initialize FFmpeg: {e}",
                {'ffmpeg': self.ffmpeg_path, 'ffprobe': self.ffprobe_path}
            )

    def _configure_gpu_acceleration(self) -> None:
        """
        Configure GPU acceleration for FFmpeg

        Sets appropriate encoder based on available GPU
        """
        gpu_info = self.gpu_manager.get_gpu_info()

        if gpu_info['cuda_available']:
            # NVIDIA GPU - use NVENC
            self.video_codec = 'h264_nvenc'
            self.logger.info("GPU acceleration enabled: NVIDIA NVENC")
        elif gpu_info['mps_available']:
            # Apple Silicon - use VideoToolbox
            self.video_codec = 'h264_videotoolbox'
            self.logger.info("GPU acceleration enabled: Apple VideoToolbox")
        else:
            self.logger.info("Using CPU encoding")

    def extract_audio(
        self,
        video_path: str,
        audio_path: str,
        audio_format: str = 'wav'
    ) -> Dict[str, Any]:
        """
        Extract audio from video using FFmpeg

        Args:
            video_path: Path to input video
            audio_path: Path to save extracted audio
            audio_format: Audio format (default: 'wav')

        Returns:
            Dict with extraction info
        """
        if not self._initialized:
            self.initialize()

        if not self.validate_video_path(video_path):
            raise ComponentException(
                "Invalid video path",
                {'video_path': video_path}
            )

        try:
            self.logger.info(f"Extracting audio from: {video_path}")

            # Build FFmpeg command
            cmd = [
                self.ffmpeg_path,
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le' if audio_format == 'wav' else self.audio_codec,
                '-ar', '16000',  # Sample rate
                '-ac', '1',  # Mono
                '-y',  # Overwrite output
                audio_path
            ]

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise ComponentException(
                    f"FFmpeg extraction failed: {result.stderr}",
                    {'command': ' '.join(cmd)}
                )

            # Get audio duration
            duration = self._get_media_duration(audio_path)

            self.logger.info(f"Audio extracted: {duration:.2f}s")

            return {
                'audio_path': audio_path,
                'duration': duration,
                'format': audio_format,
                'sample_rate': 16000
            }

        except Exception as e:
            raise ComponentException(
                f"Audio extraction failed: {e}",
                {'video': video_path, 'audio': audio_path}
            )

    def merge_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        remove_original_audio: bool = True
    ) -> Dict[str, Any]:
        """
        Merge audio with video using FFmpeg

        Args:
            video_path: Path to input video
            audio_path: Path to audio file
            output_path: Path to save output video
            remove_original_audio: Remove original audio (default: True)

        Returns:
            Dict with merge info
        """
        if not self._initialized:
            self.initialize()

        if not self.validate_video_path(video_path):
            raise ComponentException("Invalid video path", {'video_path': video_path})

        if not self.validate_audio_path(audio_path):
            raise ComponentException("Invalid audio path", {'audio_path': audio_path})

        try:
            self.logger.info(f"Merging audio with video: {output_path}")

            # Get audio and video durations
            audio_duration = self._get_media_duration(audio_path)
            video_duration = self._get_media_duration(video_path)

            # Build FFmpeg command
            if remove_original_audio:
                # Replace original audio
                # If audio is longer than video, pad video with last frame
                if audio_duration > video_duration + 0.1:  # 100ms tolerance
                    self.logger.info(
                        f"Audio ({audio_duration:.2f}s) is longer than video ({video_duration:.2f}s), "
                        f"will loop last frame to match"
                    )
                    # Use tpad to extend video to audio duration
                    pad_duration = audio_duration - video_duration
                    cmd = [
                        self.ffmpeg_path,
                        '-i', video_path,
                        '-i', audio_path,
                        '-filter_complex', f'[0:v]tpad=stop_mode=clone:stop_duration={pad_duration}[v]',
                        '-map', '[v]',
                        '-map', '1:a:0',
                        '-c:v', self.video_codec,
                        '-c:a', self.audio_codec,
                        '-b:a', self.audio_bitrate,
                        '-y',
                        output_path
                    ]
                else:
                    # Video is same length or longer
                    # DO NOT CUT VIDEO! If audio is shorter, it's a bug in audio synchronizer
                    # Just keep video full length and audio will play until it ends
                    self.logger.info(
                        f"Video ({video_duration:.2f}s) vs Audio ({audio_duration:.2f}s), "
                        f"keeping full video length"
                    )

                    if video_duration > audio_duration + 0.5:  # 500ms difference is significant
                        self.logger.warning(
                            f"Audio is {video_duration - audio_duration:.2f}s shorter than video! "
                            f"This may indicate a bug in audio synchronization."
                        )

                    # Simple copy without -shortest - keep full video length
                    cmd = [
                        self.ffmpeg_path,
                        '-i', video_path,
                        '-i', audio_path,
                        '-map', '0:v:0',
                        '-map', '1:a:0',
                        '-c:v', 'copy',
                        '-c:a', self.audio_codec,
                        '-b:a', self.audio_bitrate,
                        '-y',
                        output_path
                    ]
            else:
                # Mix with original audio
                cmd = [
                    self.ffmpeg_path,
                    '-i', video_path,
                    '-i', audio_path,
                    '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=shortest',
                    '-c:v', 'copy',
                    '-c:a', self.audio_codec,
                    '-b:a', self.audio_bitrate,
                    '-y',
                    output_path
                ]

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise ComponentException(
                    f"FFmpeg merge failed: {result.stderr}",
                    {'command': ' '.join(cmd)}
                )

            # Get output video duration
            duration = self._get_media_duration(output_path)

            self.logger.info(f"Audio merged successfully: {duration:.2f}s")

            return {
                'output_path': output_path,
                'duration': duration,
                'video_codec': 'copy',
                'audio_codec': self.audio_codec
            }

        except Exception as e:
            raise ComponentException(
                f"Audio merge failed: {e}",
                {'video': video_path, 'audio': audio_path, 'output': output_path}
            )

    def get_video_info(self, video_path: str) -> VideoInfo:
        """
        Get video file information using FFprobe

        Args:
            video_path: Path to video file

        Returns:
            VideoInfo: Video metadata
        """
        if not self._initialized:
            self.initialize()

        if not self.validate_video_path(video_path):
            raise ComponentException("Invalid video path", {'video_path': video_path})

        try:
            self.logger.info(f"Getting video info: {video_path}")

            # Build FFprobe command
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]

            # Run FFprobe
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise ComponentException(
                    f"FFprobe failed: {result.stderr}",
                    {'command': ' '.join(cmd)}
                )

            # Parse JSON output
            data = json.loads(result.stdout)

            # Extract video stream info
            video_stream = next(
                (s for s in data['streams'] if s['codec_type'] == 'video'),
                None
            )

            # Extract audio stream info
            audio_stream = next(
                (s for s in data['streams'] if s['codec_type'] == 'audio'),
                None
            )

            # Build VideoInfo
            info: VideoInfo = {
                'path': video_path,
                'duration': float(data['format'].get('duration', 0)),
                'width': video_stream.get('width', 0) if video_stream else 0,
                'height': video_stream.get('height', 0) if video_stream else 0,
                'fps': self._parse_fps(video_stream.get('r_frame_rate', '0/1')) if video_stream else 0,
                'video_codec': video_stream.get('codec_name', 'unknown') if video_stream else 'none',
                'audio_codec': audio_stream.get('codec_name', 'unknown') if audio_stream else 'none',
                'bitrate': int(data['format'].get('bit_rate', 0)),
                'size': int(data['format'].get('size', 0))
            }

            self.logger.info(f"Video info: {info['width']}x{info['height']} @ {info['fps']:.2f}fps")

            return info

        except Exception as e:
            raise ComponentException(
                f"Failed to get video info: {e}",
                {'video': video_path}
            )

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
        if not self._initialized:
            self.initialize()

        if not self.validate_video_path(input_path):
            raise ComponentException("Invalid input path", {'input_path': input_path})

        v_codec = video_codec or self.video_codec
        a_codec = audio_codec or self.audio_codec

        try:
            self.logger.info(f"Converting video: {input_path} -> {output_path}")

            # Build FFmpeg command
            cmd = [
                self.ffmpeg_path,
                '-i', input_path,
                '-c:v', v_codec,
                '-c:a', a_codec,
                '-b:a', self.audio_bitrate,
                '-y',
                output_path
            ]

            # Run FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                raise ComponentException(
                    f"FFmpeg conversion failed: {result.stderr}",
                    {'command': ' '.join(cmd)}
                )

            # Get output info
            output_info = self.get_video_info(output_path)

            self.logger.info(f"Video converted successfully: {output_info['duration']:.2f}s")

            return {
                'output_path': output_path,
                'video_codec': v_codec,
                'audio_codec': a_codec,
                'duration': output_info['duration'],
                'size': output_info['size']
            }

        except Exception as e:
            raise ComponentException(
                f"Video conversion failed: {e}",
                {'input': input_path, 'output': output_path}
            )

    def _get_media_duration(self, media_path: str) -> float:
        """
        Get media file duration using FFprobe

        Args:
            media_path: Path to media file

        Returns:
            float: Duration in seconds
        """
        try:
            cmd = [
                self.ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                media_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            return float(data['format'].get('duration', 0))

        except Exception as e:
            self.logger.warning(f"Could not get duration: {e}")
            return 0.0

    def _parse_fps(self, fps_str: str) -> float:
        """
        Parse FPS from FFprobe format (e.g., "30000/1001")

        Args:
            fps_str: FPS string

        Returns:
            float: FPS value
        """
        try:
            if '/' in fps_str:
                num, den = fps_str.split('/')
                return float(num) / float(den)
            return float(fps_str)
        except Exception:
            return 0.0

    def get_info(self) -> Dict[str, Any]:
        """
        Get FFmpeg processor information

        Returns:
            Dict: Complete processor info
        """
        info = super().get_info()
        info.update({
            'processor': 'FFmpeg',
            'ffmpeg_path': self.ffmpeg_path,
            'ffprobe_path': self.ffprobe_path,
            'gpu_acceleration': self.video_codec in ['h264_nvenc', 'hevc_nvenc', 'h264_videotoolbox']
        })
        return info

"""
Subtitle Generator
==================

Generate subtitles (SRT, VTT) from transcription and translation.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import logging


class SubtitleGenerator:
    """
    Generate subtitle files from transcription segments

    Supports multiple formats:
    - SRT (SubRip)
    - VTT (WebVTT)
    """

    def __init__(self):
        """Initialize subtitle generator"""
        self.logger = logging.getLogger('speechbridge.subtitles')

    def generate_srt(
        self,
        segments: List[Dict[str, Any]],
        texts: List[str],
        output_path: str
    ) -> str:
        """
        Generate SRT subtitle file

        Args:
            segments: Whisper segments with timing
            texts: Text for each segment (original or translated)
            output_path: Path to save SRT file

        Returns:
            str: Path to generated SRT file
        """
        if len(segments) != len(texts):
            raise ValueError(
                f"Segments count ({len(segments)}) doesn't match texts count ({len(texts)})"
            )

        srt_content = []

        for i, (seg, text) in enumerate(zip(segments, texts), 1):
            # Skip empty text
            if not text.strip():
                continue

            # Format timestamps
            start_time = self._format_srt_timestamp(seg['start'])
            end_time = self._format_srt_timestamp(seg['end'])

            # Add subtitle entry
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(text.strip())
            srt_content.append("")  # Empty line between entries

        # Write to file
        output_file = Path(output_path)
        output_file.write_text('\n'.join(srt_content), encoding='utf-8')

        self.logger.info(f"Generated SRT with {len(segments)} entries: {output_path}")

        return str(output_file)

    def generate_vtt(
        self,
        segments: List[Dict[str, Any]],
        texts: List[str],
        output_path: str
    ) -> str:
        """
        Generate VTT (WebVTT) subtitle file

        Args:
            segments: Whisper segments with timing
            texts: Text for each segment (original or translated)
            output_path: Path to save VTT file

        Returns:
            str: Path to generated VTT file
        """
        if len(segments) != len(texts):
            raise ValueError(
                f"Segments count ({len(segments)}) doesn't match texts count ({len(texts)})"
            )

        vtt_content = ["WEBVTT", ""]

        for i, (seg, text) in enumerate(zip(segments, texts), 1):
            # Skip empty text
            if not text.strip():
                continue

            # Format timestamps
            start_time = self._format_vtt_timestamp(seg['start'])
            end_time = self._format_vtt_timestamp(seg['end'])

            # Add subtitle entry
            vtt_content.append(f"{i}")
            vtt_content.append(f"{start_time} --> {end_time}")
            vtt_content.append(text.strip())
            vtt_content.append("")  # Empty line between entries

        # Write to file
        output_file = Path(output_path)
        output_file.write_text('\n'.join(vtt_content), encoding='utf-8')

        self.logger.info(f"Generated VTT with {len(segments)} entries: {output_path}")

        return str(output_file)

    def generate_dual_subtitles(
        self,
        segments: List[Dict[str, Any]],
        original_texts: List[str],
        translated_texts: List[str],
        output_path_original: str,
        output_path_translated: str,
        format: str = 'srt'
    ) -> Dict[str, str]:
        """
        Generate both original and translated subtitle files

        Args:
            segments: Whisper segments with timing
            original_texts: Original text for each segment
            translated_texts: Translated text for each segment
            output_path_original: Path for original subtitles
            output_path_translated: Path for translated subtitles
            format: Subtitle format ('srt' or 'vtt')

        Returns:
            Dict with paths to both subtitle files
        """
        result = {}

        if format.lower() == 'srt':
            result['original'] = self.generate_srt(
                segments, original_texts, output_path_original
            )
            result['translated'] = self.generate_srt(
                segments, translated_texts, output_path_translated
            )
        elif format.lower() == 'vtt':
            result['original'] = self.generate_vtt(
                segments, original_texts, output_path_original
            )
            result['translated'] = self.generate_vtt(
                segments, translated_texts, output_path_translated
            )
        else:
            raise ValueError(f"Unsupported format: {format}")

        self.logger.info(
            f"Generated dual subtitles: original={result['original']}, "
            f"translated={result['translated']}"
        )

        return result

    def _format_srt_timestamp(self, seconds: float) -> str:
        """
        Format timestamp for SRT format

        Args:
            seconds: Time in seconds

        Returns:
            str: Formatted timestamp (HH:MM:SS,mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_vtt_timestamp(self, seconds: float) -> str:
        """
        Format timestamp for VTT format

        Args:
            seconds: Time in seconds

        Returns:
            str: Formatted timestamp (HH:MM:SS.mmm)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

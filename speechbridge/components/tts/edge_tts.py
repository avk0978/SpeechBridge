"""
Edge TTS
========

Free text-to-speech using Microsoft Edge's cloud service.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import asyncio

from .base import BaseTTS
from speechbridge.core.types import TTSResult
from speechbridge.core.exceptions import ComponentException


class EdgeTTS(BaseTTS):
    """
    Microsoft Edge TTS engine

    Free, high-quality TTS using Microsoft's cloud service.
    Supports 400+ voices in 100+ languages.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize Edge TTS

        Args:
            config: Configuration with parameters:
                - voice: Voice name (default: 'en-US-AriaNeural')
                - language: Language code (default: 'en')
                - rate: Speech rate (default: 1.0)
                - pitch: Pitch adjustment (default: 0)
                - volume: Volume level (default: 100)
        """
        super().__init__(config)

        self._voices_cache = None

    def _get_default_voice(self) -> str:
        """
        Get default voice for Edge TTS

        Returns:
            str: Default voice name
        """
        return 'en-US-AriaNeural'

    def _get_voice_for_language(self, language: str) -> str:
        """
        Get appropriate voice for target language

        Args:
            language: Language code (e.g., 'ru', 'en', 'de')

        Returns:
            str: Voice name for the language
        """
        # Map language codes to default voices
        voice_map = {
            'ru': 'ru-RU-DmitryNeural',      # Russian
            'en': 'en-US-AriaNeural',        # English
            'de': 'de-DE-KatjaNeural',       # German
            'es': 'es-ES-ElviraNeural',      # Spanish
            'fr': 'fr-FR-DeniseNeural',      # French
            'it': 'it-IT-ElsaNeural',        # Italian
            'pt': 'pt-BR-FranciscaNeural',   # Portuguese
            'zh': 'zh-CN-XiaoxiaoNeural',    # Chinese
            'ja': 'ja-JP-NanamiNeural',      # Japanese
            'ko': 'ko-KR-SunHiNeural',       # Korean
            'ar': 'ar-SA-ZariyahNeural',     # Arabic
            'hi': 'hi-IN-SwaraNeural',       # Hindi
            'pl': 'pl-PL-ZofiaNeural',       # Polish
            'nl': 'nl-NL-ColetteNeural',     # Dutch
            'tr': 'tr-TR-EmelNeural',        # Turkish
            'sv': 'sv-SE-SofieNeural',       # Swedish
            'cs': 'cs-CZ-VlastaNeural',      # Czech
            'uk': 'uk-UA-PolinaNeural',      # Ukrainian
            'el': 'el-GR-AthinaNeural',      # Greek
            'ro': 'ro-RO-AlinaNeural',       # Romanian
            'hu': 'hu-HU-NoemiNeural',       # Hungarian
            'da': 'da-DK-ChristelNeural',    # Danish
            'fi': 'fi-FI-NooraNeural',       # Finnish
            'no': 'nb-NO-PernilleNeural',    # Norwegian
            'th': 'th-TH-PremwadeeNeural',   # Thai
            'vi': 'vi-VN-HoaiMyNeural',      # Vietnamese
            'id': 'id-ID-GadisNeural',       # Indonesian
            'ms': 'ms-MY-YasminNeural',      # Malay
        }

        # Get voice for language, default to English if not found
        voice = voice_map.get(language.lower(), 'en-US-AriaNeural')
        self.logger.debug(f"Selected voice {voice} for language {language}")
        return voice

    def initialize(self) -> None:
        """
        Initialize Edge TTS

        Edge TTS doesn't require initialization, but we validate the library
        """
        if self._initialized:
            return

        try:
            import edge_tts

            self.logger.info("Edge TTS initialized")
            self._initialized = True

        except ImportError:
            raise ComponentException(
                "Edge TTS library not installed",
                {'solution': 'pip install edge-tts'}
            )

    def synthesize(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        language: Optional[str] = None
    ) -> TTSResult:
        """
        Synthesize speech using Edge TTS

        Args:
            text: Text to synthesize
            output_path: Path to save audio file
            voice: Voice name (overrides config)
            language: Language code (overrides config)

        Returns:
            TTSResult: Synthesis result with metadata
        """
        # Ensure engine is initialized
        if not self._initialized:
            self.initialize()

        # Select voice: explicit voice > language-based voice > config voice
        if voice:
            voice_name = voice
        elif language:
            voice_name = self._get_voice_for_language(language)
        else:
            voice_name = self.voice

        try:
            self.logger.info(f"Synthesizing with {voice_name}: {len(text)} chars")

            # Run async synthesis
            asyncio.run(self._synthesize_async(text, output_path, voice_name))

            # Get audio duration
            duration = self._get_audio_duration(output_path)

            # Build result
            result: TTSResult = {
                'audio_path': output_path,
                'duration': duration,
                'voice': voice_name,
                'language': language or self.language,
                'text_length': len(text)
            }

            self.logger.info(f"Synthesis complete: {duration:.2f}s audio")

            return result

        except Exception as e:
            raise ComponentException(
                f"Edge TTS synthesis failed: {e}",
                {'text_length': len(text), 'voice': voice_name}
            )

    async def _synthesize_async(
        self,
        text: str,
        output_path: str,
        voice: str
    ) -> None:
        """
        Async synthesis implementation

        Args:
            text: Text to synthesize
            output_path: Output file path
            voice: Voice name
        """
        import edge_tts

        # Build SSML options for rate and pitch
        rate_str = self._format_rate(self.rate)
        pitch_str = self._format_pitch(self.pitch)
        volume_str = self._format_volume(self.volume)

        # Create communicator
        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=rate_str,
            pitch=pitch_str,
            volume=volume_str
        )

        # Save to file
        await communicate.save(output_path)

    def _format_rate(self, rate: float) -> str:
        """
        Format rate for Edge TTS

        Args:
            rate: Rate multiplier (1.0 = normal)

        Returns:
            str: Formatted rate string
        """
        if rate == 1.0:
            return "+0%"

        # Convert to percentage
        percent = int((rate - 1.0) * 100)
        sign = '+' if percent >= 0 else ''
        return f"{sign}{percent}%"

    def _format_pitch(self, pitch: int) -> str:
        """
        Format pitch for Edge TTS

        Args:
            pitch: Pitch adjustment (-20 to 20)

        Returns:
            str: Formatted pitch string
        """
        if pitch == 0:
            return "+0Hz"

        # Edge TTS uses Hz, approximate conversion
        hz = int(pitch * 10)
        sign = '+' if hz >= 0 else ''
        return f"{sign}{hz}Hz"

    def _format_volume(self, volume: int) -> str:
        """
        Format volume for Edge TTS

        Args:
            volume: Volume level (0-100)

        Returns:
            str: Formatted volume string
        """
        # Edge TTS uses percentage relative to default
        percent = int((volume - 100) * 0.5)
        sign = '+' if percent >= 0 else ''
        return f"{sign}{percent}%"

    def _get_audio_duration(self, audio_path: str) -> float:
        """
        Get audio file duration

        Args:
            audio_path: Path to audio file

        Returns:
            float: Duration in seconds
        """
        try:
            # Try using ffprobe first (works for all formats)
            import subprocess
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    audio_path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())

            # Fallback to wave module for WAV files
            import wave
            with wave.open(audio_path, 'rb') as audio:
                frames = audio.getnframes()
                rate = audio.getframerate()
                duration = frames / float(rate)
                return duration

        except Exception as e:
            self.logger.warning(f"Could not get audio duration: {e}")
            return 0.0

    def get_available_voices(self, language: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get available Edge TTS voices

        Args:
            language: Filter by language (optional)

        Returns:
            List of voice info dictionaries
        """
        if not self._initialized:
            self.initialize()

        try:
            # Cache voices to avoid repeated API calls
            if self._voices_cache is None:
                import edge_tts
                self._voices_cache = asyncio.run(edge_tts.list_voices())

            voices = self._voices_cache

            # Filter by language if specified
            if language:
                voices = [
                    v for v in voices
                    if v.get('Locale', '').lower().startswith(language.lower())
                ]

            # Format voice info
            result = []
            for voice in voices:
                result.append({
                    'name': voice.get('ShortName', ''),
                    'language': voice.get('Locale', ''),
                    'gender': voice.get('Gender', ''),
                    'locale_name': voice.get('LocalName', '')
                })

            return result

        except Exception as e:
            self.logger.error(f"Failed to get voices: {e}")
            return []

    def synthesize_batch(
        self,
        texts: List[str],
        output_dir: str,
        voice: Optional[str] = None,
        language: Optional[str] = None
    ) -> List[TTSResult]:
        """
        Synthesize multiple texts (async batch for better performance)

        Args:
            texts: List of texts to synthesize
            output_dir: Directory to save audio files
            voice: Voice name (overrides config)
            language: Language code (overrides config)

        Returns:
            List[TTSResult]: List of synthesis results
        """
        if not self._initialized:
            self.initialize()

        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)

        voice_name = voice or self.voice

        self.logger.info(f"Batch synthesizing {len(texts)} texts")

        # Run async batch synthesis
        results = asyncio.run(
            self._synthesize_batch_async(texts, output_path, voice_name, language)
        )

        self.logger.info(f"Batch synthesis complete: {len(results)} files")

        return results

    async def _synthesize_batch_async(
        self,
        texts: List[str],
        output_dir: Path,
        voice: str,
        language: Optional[str]
    ) -> List[TTSResult]:
        """
        Async batch synthesis implementation

        Args:
            texts: List of texts
            output_dir: Output directory
            voice: Voice name
            language: Language code

        Returns:
            List[TTSResult]: Synthesis results
        """
        import edge_tts

        tasks = []
        output_paths = []

        # Create tasks for all texts
        for i, text in enumerate(texts):
            file_path = output_dir / f"speech_{i:04d}.wav"
            output_paths.append(str(file_path))

            rate_str = self._format_rate(self.rate)
            pitch_str = self._format_pitch(self.pitch)
            volume_str = self._format_volume(self.volume)

            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=rate_str,
                pitch=pitch_str,
                volume=volume_str
            )

            tasks.append(communicate.save(str(file_path)))

        # Execute all tasks concurrently
        await asyncio.gather(*tasks)

        # Build results
        results = []
        for i, (text, path) in enumerate(zip(texts, output_paths)):
            duration = self._get_audio_duration(path)
            result: TTSResult = {
                'audio_path': path,
                'duration': duration,
                'voice': voice,
                'language': language or self.language,
                'text_length': len(text)
            }
            results.append(result)

        return results

    def get_info(self) -> Dict[str, Any]:
        """
        Get Edge TTS information

        Returns:
            Dict: Complete TTS info
        """
        info = super().get_info()
        info.update({
            'engine': 'Edge TTS',
            'free': True,
            'cloud_based': True
        })
        return info

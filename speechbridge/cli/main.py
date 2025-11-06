"""
SpeechBridge CLI Main
=====================

Main command-line interface entry point.
"""

import click
import sys
from pathlib import Path
from typing import Optional

from ..core.builder import PipelineBuilder, create_pipeline
from ..utils.logging import setup_logging
from ..__version__ import __version__


@click.group()
@click.version_option(version=__version__, prog_name='SpeechBridge')
@click.option('--log-dir', default='logs', help='Log directory')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, log_dir, verbose):
    """
    SpeechBridge - Video Translation Framework

    Translate videos to any language using AI.
    """
    # Setup logging (always enable console output for CLI)
    ctx.ensure_object(dict)
    ctx.obj['logger_system'] = setup_logging(
        log_dir=log_dir,
        console_output=True  # Always show logs in CLI
    )
    ctx.obj['logger'] = ctx.obj['logger_system'].get_logger('cli')
    ctx.obj['verbose'] = verbose


@cli.command()
@click.argument('video_path', type=click.Path(exists=True))
@click.argument('output_path', type=click.Path())
@click.option('--model', '-m', default='base',
              help='Whisper model: tiny, base, small, medium, large')
@click.option('--source-lang', '-s', default='auto',
              help='Source language (auto-detect if not specified)')
@click.option('--target-lang', '-t', default='en',
              help='Target language')
@click.option('--deepl-key', envvar='DEEPL_API_KEY',
              help='DeepL API key (or use DEEPL_API_KEY env var)')
@click.option('--voice', default=None,
              help='TTS voice name (e.g., en-US-AriaNeural)')
@click.option('--rate', default=1.0, type=float,
              help='Speech rate (0.5-2.0, default: 1.0)')
@click.option('--sync/--no-sync', default=True,
              help='Synchronize audio with original timing (default: enabled)')
@click.option('--subtitles/--no-subtitles', default=False,
              help='Generate subtitle files (default: disabled)')
@click.option('--subtitle-format', type=click.Choice(['srt', 'vtt', 'both']), default='srt',
              help='Subtitle format (default: srt)')
@click.option('--subtitle-only', is_flag=True,
              help='Only generate subtitles, no audio translation')
@click.option('--embed-subtitles', is_flag=True,
              help='Embed subtitles into video file (works with --subtitles)')
@click.option('--export-text', is_flag=True,
              help='Export translation text with timing as JSON')
@click.option('--temp-dir', default='temp',
              help='Temporary files directory')
@click.option('--keep-temp', is_flag=True,
              help='Keep temporary files')
@click.pass_context
def translate(ctx, video_path, output_path, model, source_lang, target_lang,
              deepl_key, voice, rate, sync, subtitles, subtitle_format,
              subtitle_only, embed_subtitles, export_text, temp_dir, keep_temp):
    """
    Translate a video to target language.

    Example:
        speechbridge translate input.mp4 output.mp4 -t ru --model base
    """
    logger = ctx.obj['logger']

    try:
        # Display configuration
        click.echo(f"\n{'='*60}")
        click.echo(f"SpeechBridge Video Translation")
        click.echo(f"{'='*60}")
        click.echo(f"Input:  {video_path}")
        click.echo(f"Output: {output_path}")
        click.echo(f"Model:  {model}")
        click.echo(f"Source: {source_lang}")
        click.echo(f"Target: {target_lang}")
        click.echo(f"{'='*60}\n")

        # Progress callback
        def progress_callback(percent, message):
            click.echo(f"[{percent:3d}%] {message}")

        # Build pipeline
        logger.info("Building pipeline...")
        builder = (PipelineBuilder()
                   .with_whisper(model=model, language=source_lang)
                   .with_deepl(api_key=deepl_key, target_lang=target_lang)
                   .with_edge_tts(rate=rate)
                   .with_ffmpeg()
                   .with_temp_dir(temp_dir)
                   .with_progress_callback(progress_callback)
                   .keep_temporary_files(keep_temp))

        # Configure synchronization
        if sync:
            builder._pipeline_config['sync_audio'] = True
            click.echo("Audio synchronization: ENABLED")
        else:
            builder._pipeline_config['sync_audio'] = False
            click.echo("Audio synchronization: DISABLED")

        # Configure subtitles
        if subtitles or subtitle_only:
            builder._pipeline_config['generate_subtitles'] = True
            builder._pipeline_config['subtitle_format'] = subtitle_format
            click.echo(f"Subtitle generation: ENABLED ({subtitle_format})")

        if subtitle_only:
            builder._pipeline_config['subtitle_only'] = True
            click.echo("Mode: SUBTITLE-ONLY (no audio translation)")

        if embed_subtitles:
            if not (subtitles or subtitle_only):
                click.echo("Warning: --embed-subtitles requires --subtitles or --subtitle-only")
                click.echo("         Enabling subtitle generation automatically")
                builder._pipeline_config['generate_subtitles'] = True
            builder._pipeline_config['embed_subtitles'] = True
            click.echo("Subtitle embedding: ENABLED (subtitles will be embedded in video)")

        # Configure text export
        if export_text:
            builder._pipeline_config['export_text'] = True
            click.echo("Text export with timing: ENABLED")

        if voice:
            builder._tts_engine.voice = voice

        pipeline = builder.build()

        # Validate components
        click.echo("\nValidating components...")
        if not pipeline.validate_components():
            click.echo(click.style("\n✗ Pipeline validation failed!", fg='red'))
            click.echo("\nPlease check:")
            click.echo("  1. DeepL API key is set (--deepl-key or DEEPL_API_KEY env var)")
            click.echo("  2. FFmpeg is installed (run: ffmpeg -version)")
            click.echo("  3. Check logs in logs/speechbridge_current.log for details")
            sys.exit(1)

        click.echo(click.style("✓ Pipeline configured successfully", fg='green'))

        # Process video
        logger.info("Starting video translation...")
        result = pipeline.process_video(video_path, output_path)

        # Display result
        click.echo()
        if result['success']:
            if result['metadata'].get('subtitle_only_mode'):
                click.echo(click.style("✓ Subtitle generation completed successfully!", fg='green'))
            else:
                click.echo(click.style("✓ Translation completed successfully!", fg='green'))

            click.echo(f"\nOutput: {result['output_path']}")

            if 'transcription' in result:
                click.echo(f"\nTranscribed text ({result['transcription']['language']}):")
                click.echo(f"  {result['transcription']['text'][:100]}...")

            if 'translation' in result:
                click.echo(f"\nTranslated text ({result['translation']['target_lang']}):")
                click.echo(f"  {result['translation']['text'][:100]}...")

            if 'subtitle_files' in result and result['subtitle_files']:
                if result['metadata'].get('subtitles_embedded'):
                    click.echo(f"\n✓ Subtitles embedded in video:")
                    click.echo(f"  View in QuickTime: View → Subtitles")
                    click.echo(f"  Or press: Option+Command+C")
                    click.echo(f"\nSubtitle tracks included:")
                    for subtitle_file in result['subtitle_files']:
                        if subtitle_file.endswith('.srt'):
                            click.echo(f"  - {Path(subtitle_file).stem}")
                    click.echo(f"\nExternal subtitle files also saved:")
                    for subtitle_file in result['subtitle_files']:
                        click.echo(f"  - {Path(subtitle_file).name}")
                else:
                    click.echo(f"\nSubtitle files generated:")
                    for subtitle_file in result['subtitle_files']:
                        click.echo(f"  - {Path(subtitle_file).name}")

            if 'text_export' in result:
                click.echo(f"\nText export saved:")
                click.echo(f"  - {Path(result['text_export']).name}")

            if 'tts' in result:
                click.echo(f"\nSynthesis: {result['tts']['duration']:.2f}s audio")
        else:
            click.echo(click.style("✗ Translation failed!", fg='red'))
            for error in result.get('errors', []):
                click.echo(f"  Error: {error}")
            sys.exit(1)

    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        click.echo(click.style(f"\n✗ Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.argument('video_dir', type=click.Path(exists=True))
@click.argument('output_dir', type=click.Path())
@click.option('--model', '-m', default='base',
              help='Whisper model')
@click.option('--target-lang', '-t', default='en',
              help='Target language')
@click.option('--deepl-key', envvar='DEEPL_API_KEY',
              help='DeepL API key')
@click.option('--pattern', default='*.mp4',
              help='File pattern (default: *.mp4)')
@click.pass_context
def batch(ctx, video_dir, output_dir, model, target_lang, deepl_key, pattern):
    """
    Translate multiple videos in batch.

    Example:
        speechbridge batch videos/ translated/ -t ru --pattern "*.mp4"
    """
    logger = ctx.obj['logger']

    try:
        # Find videos
        video_path = Path(video_dir)
        videos = list(video_path.glob(pattern))

        if not videos:
            click.echo(f"No videos found matching pattern: {pattern}")
            sys.exit(1)

        click.echo(f"\nFound {len(videos)} videos to process")

        # Build pipeline
        pipeline = create_pipeline(
            speech_model=model,
            target_language=target_lang,
            deepl_api_key=deepl_key
        )

        # Process batch
        results = pipeline.process_video_batch(
            [str(v) for v in videos],
            output_dir
        )

        # Display summary
        success_count = sum(1 for r in results if r['success'])
        click.echo(f"\n{'='*60}")
        click.echo(f"Batch processing complete:")
        click.echo(f"  Success: {success_count}/{len(videos)}")
        click.echo(f"  Failed:  {len(videos) - success_count}/{len(videos)}")
        click.echo(f"{'='*60}")

    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        click.echo(click.style(f"\n✗ Error: {e}", fg='red'))
        sys.exit(1)


@cli.command()
@click.pass_context
def info(ctx):
    """
    Display system and GPU information.
    """
    from ..core.gpu import GPUManager

    gpu = GPUManager()
    gpu_info = gpu.get_gpu_info()

    click.echo(f"\nSpeechBridge Framework v{__version__}")
    click.echo(f"{'='*60}")

    click.echo("\nGPU Information:")
    click.echo(f"  Optimal device: {gpu_info['optimal_device']}")
    click.echo(f"  CUDA available: {gpu_info['cuda_available']}")
    if gpu_info['cuda_available']:
        click.echo(f"  CUDA devices:   {gpu_info['cuda_devices']}")
        click.echo(f"  Device name:    {gpu_info['cuda_device_name']}")
    click.echo(f"  MPS available:  {gpu_info['mps_available']}")

    click.echo("\nSupported Components:")
    click.echo("  Speech Recognition: Whisper (99+ languages)")
    click.echo("  Translation:        DeepL (31+ languages)")
    click.echo("  Text-to-Speech:     Edge TTS (400+ voices)")
    click.echo("  Video Processing:   FFmpeg")

    click.echo()


@cli.command()
def test():
    """
    Run framework tests.
    """
    import pytest
    from pathlib import Path

    tests_dir = Path(__file__).parent.parent / 'tests'

    click.echo("Running SpeechBridge tests...\n")

    result = pytest.main([
        str(tests_dir),
        '-v',
        '--tb=short'
    ])

    sys.exit(result)


@cli.command()
@click.argument('video_path', type=click.Path(exists=True))
@click.pass_context
def analyze(ctx, video_path):
    """
    Analyze a video file and display information.

    Example:
        speechbridge analyze video.mp4
    """
    logger = ctx.obj['logger']

    try:
        from ..components.video.processor import FFmpegProcessor

        processor = FFmpegProcessor()
        processor.initialize()

        info = processor.get_video_info(video_path)

        click.echo(f"\nVideo Analysis: {video_path}")
        click.echo(f"{'='*60}")
        click.echo(f"Duration:     {info['duration']:.2f} seconds")
        click.echo(f"Resolution:   {info['width']}x{info['height']}")
        click.echo(f"FPS:          {info['fps']:.2f}")
        click.echo(f"Video codec:  {info['video_codec']}")
        click.echo(f"Audio codec:  {info['audio_codec']}")
        click.echo(f"Bitrate:      {info['bitrate'] / 1000:.0f} kbps")
        click.echo(f"File size:    {info['size'] / (1024*1024):.2f} MB")
        click.echo(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        click.echo(click.style(f"\n✗ Error: {e}", fg='red'))
        sys.exit(1)


if __name__ == '__main__':
    cli()

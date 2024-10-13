"""Microsoft TTS."""

import logging
import tempfile
import time
import asyncio
import ctypes
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk

_LOGGER = logging.getLogger(__name__)

ssml_template = """
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" xml:lang="{lang}">
  <voice name="{voice_name}">
      <lang xml:lang="{inner_lang}">
        {prosody_start}{text}{prosody_end}
      </lang>
  </voice>
</speak>
"""


class MicrosoftTTS:
    """Class to handle Microsoft TTS."""

    def __init__(self, args) -> None:
        """Initialize."""
        _LOGGER.debug("Initialize Microsoft TTS")
        self.args = args
        self.speech_config = speechsdk.SpeechConfig(
            subscription=args.subscription_key, region=args.service_region
        )

        # output_dir = str(tempfile.TemporaryDirectory())
        # output_dir = Path(output_dir)
        # output_dir.mkdir(parents=True, exist_ok=True)
        # self.output_dir = output_dir

    # Function to generate SSML string with optional prosody
    def generate_ssml(
        self, voice_name, lang, inner_lang, text, rate=None, pitch=None, contour=None
    ):
        if rate or pitch or contour:
            prosody_start = f'<prosody rate="{rate if rate else "0%"}" pitch="{pitch if pitch else "0%"}" contour="{contour if contour else ""}">'
            prosody_end = "</prosody>"
        else:
            prosody_start = ""
            prosody_end = ""

        return ssml_template.format(
            voice_name=voice_name,
            lang=lang,
            inner_lang=inner_lang,
            text=text,
            prosody_start=prosody_start,
            prosody_end=prosody_end,
        )

    def synthesize_stream(self, text, voice=None, samples_per_chunk=None):
        """Synthesize text to speech and return a stream."""
        _LOGGER.debug(f"Requested TTS for [{text}]")
        if voice is None:
            voice = self.args.voice

        if samples_per_chunk is None:
            samples_per_chunk = self.args.samples_per_chunk

        self.speech_config.speech_synthesis_voice_name = voice
        self.speech_config.speech_synthesis_language = "es-MX"

        # Use PullAudioOutputStream to get the audio data as a stream
        pull_stream = speechsdk.audio.PullAudioOutputStream()
        audio_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config, audio_config=audio_config
        )

        speech_synthesis_result = speech_synthesizer.start_speaking_text_async(text)

        # Wait for the operation to complete
        result = speech_synthesis_result.get()

        # Access the in-memory audio data
        buffer = (ctypes.c_ubyte * samples_per_chunk)()

        while True:
            audio_chunk = pull_stream.read(buffer)
            if not audio_chunk:
                break
            yield bytes(buffer[:audio_chunk])

    def synthesize_stream_ssml(self, text, voice=None, samples_per_chunk=None):
        """Synthesize text to speech and return a stream."""
        ssml = self.generate_ssml(
            voice,
            lang=self.args.language,
            inner_lang=self.args.language,
            text=text,
            rate=self.args.rate,
        )

        _LOGGER.debug(f"Requested TTS for [{text}]")
        if voice is None:
            voice = self.args.voice

        if samples_per_chunk is None:
            samples_per_chunk = self.args.samples_per_chunk

        self.speech_config.speech_synthesis_voice_name = voice

        # Use PullAudioOutputStream to get the audio data as a stream
        pull_stream = speechsdk.audio.PullAudioOutputStream()
        audio_config = speechsdk.audio.AudioOutputConfig(stream=pull_stream)

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config, audio_config=audio_config
        )

        speech_synthesis_result = speech_synthesizer.start_speaking_ssml_async(ssml)

        # Wait for the operation to complete
        result = speech_synthesis_result.get()

        # Access the in-memory audio data
        buffer = (ctypes.c_ubyte * samples_per_chunk)()

        while True:
            audio_chunk = pull_stream.read(buffer)
            if not audio_chunk:
                _LOGGER.debug("Ended transcription")
                break
            yield bytes(buffer[:audio_chunk])

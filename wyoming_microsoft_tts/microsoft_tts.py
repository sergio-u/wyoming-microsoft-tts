"""Microsoft TTS."""

import logging
import tempfile
import time
import asyncio
import ctypes
from pathlib import Path
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine, TypeVar

import azure.cognitiveservices.speech as speechsdk

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

ssml_template = """
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" xml:lang="{lang}">
  <voice name="{voice_name}">
      <lang xml:lang="{inner_lang}">
        {prosody_start}{text}{prosody_end}
      </lang>
  </voice>
</speak>
"""

__all__ = [
    "run_coroutine_sync",
]

T = TypeVar("T")


def run_coroutine_sync(coroutine: Coroutine[Any, Any, T], timeout: float = 30) -> T:
    def run_in_new_loop():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coroutine)
        finally:
            new_loop.close()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    if threading.current_thread() is threading.main_thread():
        if not loop.is_running():
            return loop.run_until_complete(coroutine)
        else:
            with ThreadPoolExecutor() as pool:
                future = pool.submit(run_in_new_loop)
                return future.result(timeout=timeout)
    else:
        return asyncio.run_coroutine_threadsafe(coroutine, loop).result()


class PushAudioOutputStreamCallback(speechsdk.audio.PushAudioOutputStreamCallback):
    def __init__(self, on_audio_start, on_audio_chunk, on_audio_stop):
        super().__init__()
        self.on_audio_start = on_audio_start
        self.on_audio_chunk = on_audio_chunk
        self.on_audio_stop = on_audio_stop
        self.first_chunk = True
        self._audio_data = bytes(0)
        self.closed = False

    def write(self, audio_buffer: memoryview) -> int:
        if self.first_chunk:
            run_coroutine_sync(self.on_audio_start())
            self.first_chunk = False

        self._audio_data += audio_buffer
        run_coroutine_sync(self.on_audio_chunk(bytes(audio_buffer)))
        _LOGGER.debug(f"{audio_buffer.nbytes} bytes received.")
        return audio_buffer.nbytes

    def close(self):
        self.closed = True
        run_coroutine_sync(self.on_audio_stop())
        _LOGGER.debug("Push audio output stream closed.")

    def get_audio_size(self) -> int:
        return len(self._audio_data)


class MicrosoftTTS:
    """Class to handle Microsoft TTS."""

    def __init__(self, args) -> None:
        """Initialize."""
        _LOGGER.debug("Initialize Microsoft TTS")
        self.args = args
        self.speech_config = speechsdk.SpeechConfig(
            subscription=args.subscription_key, region=args.service_region
        )

    # Function to generate SSML string with optional prosody
    def generate_ssml(
        self, voice_name, lang, inner_lang, text, rate=None, pitch=None, contour=None
    ):
        if rate or pitch or contour:
            prosody_start = f'<prosody rate="{rate if rate else "1"}" pitch="{pitch if pitch else "1"}" contour="{contour if contour else ""}">'
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

    def synthesize_stream_ssml(
        self,
        text,
        push_callback,
        voice=None,
        language=None,
        samples_per_chunk=None,
    ):
        """Synthesize text to speech and return a stream."""

        _LOGGER.debug(f"Requested TTS for [{text}]")
        if voice is None:
            voice = self.args.voice
        else:
            _LOGGER.debug(f"Using voice [{voice}]")

        if language is None:
            language = self.args.language
        else:
            _LOGGER.debug(f"Using language [{language}]")

        ssml = self.generate_ssml(
            voice,
            lang=language,
            inner_lang=language,
            text=text,
            # rate=self.args.rate,
        )
        _LOGGER.debug(f"SSML: {ssml}")

        if samples_per_chunk is None:
            samples_per_chunk = self.args.samples_per_chunk

        self.speech_config.speech_synthesis_voice_name = voice

        # Use PullAudioOutputStream to get the audio data as a stream
        push_stream = speechsdk.audio.PushAudioOutputStream(push_callback)
        audio_config = speechsdk.audio.AudioOutputConfig(stream=push_stream)

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config, audio_config=audio_config
        )

        # Receives a text from console input and synthesizes it to stream output.
        result = speech_synthesizer.speak_ssml_async(ssml).get()
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            _LOGGER.info(
                f"Speech synthesized for text [{text}], and the audio was written to output stream."
            )
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            _LOGGER.error(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                _LOGGER.error(f"Error details: {cancellation_details.error_details}")
        del result
        del speech_synthesizer

        return

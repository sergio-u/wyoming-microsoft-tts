"""Event handler for clients of the server."""

import argparse
import logging
import math
import os
import wave
import json

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler
from wyoming.tts import Synthesize

from .microsoft_tts import MicrosoftTTS, PushAudioOutputStreamCallback

_LOGGER = logging.getLogger(__name__)


class MicrosoftEventHandler(AsyncEventHandler):
    """Event handler for clients of the server."""

    def __init__(
        self,
        wyoming_info: Info,
        cli_args: argparse.Namespace,
        *args,
        **kwargs,
    ) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.wyoming_info_event = wyoming_info.event()
        self.microsoft_tts = MicrosoftTTS(cli_args)

        self.rate = 16000
        self.width = 2
        self.channels = 1

    async def start_audio(self):
        return await self.write_event(
            AudioStart(rate=16000, width=2, channels=1).event()
        )

    async def chunk_audio(self, audio_chunk):
        return await self.write_event(
            AudioChunk(
                audio=audio_chunk,
                rate=self.rate,
                width=self.width,
                channels=self.channels,
            ).event()
        )

    async def end_audio(self):
        return await self.write_event(AudioStop().event())

    async def handle_event(self, event: Event) -> bool:
        """Handle an event."""
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info")
            return True

        if not Synthesize.is_type(event.type):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        synthesize = Synthesize.from_event(event)
        _LOGGER.debug(synthesize)
        _LOGGER.debug(json.dumps(event.data))

        raw_text = synthesize.text

        # Join multiple lines
        text = " ".join(raw_text.strip().splitlines())

        # Create push class
        push = PushAudioOutputStreamCallback(
            self.start_audio, self.chunk_audio, self.end_audio
        )

        # Use the new streaming synthesis method
        self.microsoft_tts.synthesize_stream_ssml(
            text=text, voice=synthesize.voice.name, push_callback=push
        )

        return True

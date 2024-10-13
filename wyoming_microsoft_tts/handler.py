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

from .microsoft_tts import MicrosoftTTS

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

        # Use the new streaming synthesis method
        audio_stream = self.microsoft_tts.synthesize_stream_ssml(
            text=text, voice=synthesize.voice.name
        )

        # Assume 16-bit PCM audio, mono
        rate = 16000  # You may need to adjust this based on the actual output
        width = 2
        channels = 1

        await self.write_event(
            AudioStart(
                rate=rate,
                width=width,
                channels=channels,
            ).event(),
        )

        for audio_chunk in audio_stream:
            _LOGGER.debug(f"Received chunk: {len(audio_chunk)} bytes")
            await self.write_event(
                AudioChunk(
                    audio=audio_chunk,
                    rate=rate,
                    width=width,
                    channels=channels,
                ).event(),
            )

        await self.write_event(AudioStop().event())
        _LOGGER.debug("Completed request")

        return True

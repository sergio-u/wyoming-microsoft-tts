import argparse  # noqa: D100
import asyncio
import contextlib
import logging
from functools import partial
from typing import Any

from wyoming.info import Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer

from wyoming_microsoft_tts.download import get_voices
from wyoming_microsoft_tts.handler import MicrosoftEventHandler
from wyoming_microsoft_tts.version import __version__

_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Start Wyoming Microsoft TTS server."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--service-region",
        required=True,
        help="Microsoft Azure region (e.g., westus2)",
    )
    parser.add_argument(
        "--subscription-key",
        required=True,
        help="Microsoft Azure subscription key",
    )
    parser.add_argument(
        "--voice",
        default="en-GB-SoniaNeural",
        help="Default Microsoft voice to use (e.g., en-GB-SoniaNeural)",
    )
    parser.add_argument(
        "--uri", default="tcp://0.0.0.0:10200", help="unix:// or tcp://"
    )
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    parser.add_argument(
        "--update-voices",
        action="store_true",
        help="Download latest voices.json during startup",
    )
    parser.add_argument(
        "--download-dir",
        default="/tmp/",
        type=str,
        help="Directory to download voices.json into (default: /tmp/)",
    )
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument("--language", type=str, help="Language code")
    parser.add_argument("--rate", type=float, help="Speech rate percentage")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Load voice info
    voices_info = get_voices(
        args.download_dir,
        update_voices=args.update_voices,
        region=args.service_region,
        key=args.subscription_key,
    )

    # Resolve aliases for backwards compatibility with old voice names
    aliases_info: dict[str, Any] = {}
    for voice_info in voices_info.values():
        for voice_alias in voice_info.get("aliases", []):
            aliases_info[voice_alias] = {"_is_alias": True, **voice_info}

    voices_info.update(aliases_info)
    voices = [
        TtsVoice(
            name=voice_name,
            description=get_description(voice_info),
            attribution=Attribution(
                name="Microsoft",
                url="https://github.com/sergio-u/wyoming-microsoft-tts",
            ),
            installed=True,
            version=__version__,
            languages=[
                voice_info.get("language", {}).get(
                    "code",
                    voice_info.get("espeak", {}).get("voice", voice_name.split("_")[0]),
                ),
                voice_info.get("secondary_languages", []),
            ],
        )
        for voice_name, voice_info in voices_info.items()
        if not voice_info.get("_is_alias", False)
    ]

    wyoming_info = Info(
        tts=[
            TtsProgram(
                name="microsoft-tts-stream",
                description="A fast, local, neural text to speech engine",
                attribution=Attribution(
                    name="Microsoft",
                    url="https://github.com/sergio-u/wyoming-microsoft-tts",
                ),
                installed=True,
                version=__version__,
                voices=sorted(voices, key=lambda v: v.name),
            )
        ],
    )

    # Start server
    server = AsyncServer.from_uri(args.uri)

    _LOGGER.info("Ready")
    await server.run(
        partial(
            MicrosoftEventHandler,
            wyoming_info,
            args,
        )
    )


# -----------------------------------------------------------------------------


def get_description(voice_info: dict[str, Any]):
    """Get a human readable description for a voice."""
    name = voice_info["name"]
    name = " ".join(name.split("_"))
    quality = voice_info["quality"]

    return f"{name} ({quality})"


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())

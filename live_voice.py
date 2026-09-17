import asyncio
import os
import sys

import numpy as np
import sounddevice as sd

from google import genai
from google.genai import types


MODEL = "models/gemini-3.8-live"

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = 1024

SYSTEM_PROMPT = """
You are JARVIS V4, Boss's personal AI assistant.

PERSONALITY:
- Intelligent, calm, confident and natural.
- Slightly witty when appropriate.
- Address the user as Boss naturally.
- Keep spoken answers concise.
- Do not give unnecessary explanations.
- Never claim to have performed an action unless it actually happened.

This is a real-time voice conversation.
Respond naturally and quickly.
"""


async def microphone_sender(session):
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=20)

    def callback(indata, frames, time_info, status):
        if status:
            print(f"[MIC] {status}", file=sys.stderr)

        data = indata.copy().tobytes()

        try:
            loop.call_soon_threadsafe(queue.put_nowait, data)
        except asyncio.QueueFull:
            pass

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=BLOCK_SIZE,
        callback=callback,
    )

    stream.start()

    print("🎤 Live microphone active")

    try:
        while True:
            data = await queue.get()

            await session.send_realtime_input(
                audio=types.Blob(
                    data=data,
                    mime_type="audio/pcm;rate=16000",
                )
            )

    finally:
        stream.stop()
        stream.close()


async def speaker_receiver(session):
    print("🔊 Live audio receiver active")

    while True:
        async for response in session.receive():

            if response.data:
                # Gemini Live audio is PCM.
                audio = np.frombuffer(
                    response.data,
                    dtype=np.int16,
                )

                sd.play(
                    audio,
                    samplerate=24000,
                    blocking=True,
                )

            if response.text:
                print(f"\nJARVIS: {response.text}")


async def main():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set."
        )

    client = genai.Client(api_key=api_key)

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=SYSTEM_PROMPT,

        # Keep reasoning minimal for fast conversational response.
        thinking_config=types.ThinkingConfig(
            thinking_budget=0,
        ),

        # Let Gemini handle speech activity detection.
        realtime_input_config=types.RealtimeInputConfig(),

        # Native output speech.
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Puck",
                )
            )
        ),
    )

    print("=" * 45)
    print("        JARVIS LIVE VOICE")
    print("=" * 45)
    print("Connecting...")

    async with client.aio.live.connect(
        model=MODEL,
        config=config,
    ) as session:

        print("🟢 JARVIS LIVE CONNECTED")
        print("Speak normally. Press Ctrl+C to stop.\n")

        await asyncio.gather(
            microphone_sender(session),
            speaker_receiver(session),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\n\nJARVIS Live stopped.")

import os
import subprocess
import tempfile

from groq import Groq


MODEL = "canopylabs/orpheus-v1-english"
VOICE = "troy"


class VoiceInfo:
    name = "Groq Orpheus - Troy"


VOICE_INFO = VoiceInfo()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])


def speak(text):
    text = str(text).strip()

    if not text:
        return

    print(f"JARVIS: {text}")

    wav_path = None

    try:
        # Generate speech with Groq Orpheus
        response = _client.audio.speech.create(
            model=MODEL,
            voice=VOICE,
            input=text,
            response_format="wav",
        )

        # Temporary WAV file for fast local playback
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        ) as f:
            wav_path = f.name
            f.write(response.read())

        # Play through ALSA
        subprocess.run(
            ["aplay", "-q", wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    except Exception as e:
        print(f"[TTS ERROR] {e}")

    finally:
        if wav_path:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

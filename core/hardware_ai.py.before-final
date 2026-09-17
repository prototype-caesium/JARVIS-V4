import json
from google import genai
import os

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

MODEL = "gemini-3.5-flash-lite"

PROMPT = """
You are JARVIS hardware command parser.

Convert the user's request into JSON.

Allowed actions ONLY:

LED:
{"action":"led","target":"1","state":"on"}
{"action":"led","target":"1","state":"off"}
{"action":"led","target":"2","state":"on"}
{"action":"led","target":"2","state":"off"}
{"action":"led","target":"3","state":"on"}
{"action":"led","target":"3","state":"off"}
{"action":"led","target":"all","state":"on"}
{"action":"led","target":"all","state":"off"}

If the request is NOT an LED command, return:
{"action":"none"}

Return ONLY valid JSON.
"""


def parse_hardware_command(text):
    try:
        response = client.interactions.create(
            model=MODEL,
            system_instruction=PROMPT,
            input=text,
        )

        result = response.output_text.strip()

        # Remove accidental markdown fences
        result = result.replace("```json", "").replace("```", "").strip()

        return json.loads(result)

    except Exception as e:
        print(f"❌ Hardware AI error: {e}")
        return {"action": "none"}

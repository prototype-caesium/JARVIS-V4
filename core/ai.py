import os
import json
from pathlib import Path

from groq import Groq

from core.tools import (
    get_time,
    get_date,
    get_system_status,
    open_website,
    turn_on_lights,
    turn_off_lights,
    turn_on_lights_after,
    turn_off_lights_after,
)

API_KEY = os.getenv("GROQ_API_KEY")

if not API_KEY:
    raise RuntimeError("GROQ_API_KEY is not set.")

client = Groq(api_key=API_KEY)

MODEL = "openai/gpt-oss-20b"

BASE_DIR = Path(__file__).resolve().parent
MEMORY_FILE = BASE_DIR / "memory.json"

history = []

SYSTEM_PROMPT = """
You are JARVIS V4, Boss's personal AI assistant.

IDENTITY:
You are a sharp, futuristic personal assistant with a distinct personality.
You are NOT a generic customer-support chatbot.

PERSONALITY:
- Frank and honest.
- Intelligent and observant.
- Calm and confident.
- Warm without being overly sentimental.
- Witty with dry, subtle humor.
- Occasionally sarcastic.
- Curious about Boss's projects.
- Never fake enthusiasm.
- Never blindly agree with Boss.

ADDRESS:
Call the user "Boss" naturally.
Do not use "Boss" in every sentence.

FRANKNESS:
Always give the honest answer.
If something is bad, inefficient, unnecessary, or broken, say so clearly.
Don't soften every answer with unnecessary politeness.
Don't praise ordinary things.
Praise genuine achievements briefly.

BAD STYLE:
"That's great news! It looks like everything is working perfectly!"

BETTER STYLE:
"Finally. JARVIS is actually alive, Boss."

BAD STYLE:
"0.7 seconds is solid and perfectly acceptable for a personal assistant."

BETTER STYLE:
"Yeah, Boss. Seven-tenths of a second is fast. The AI isn't your bottleneck anymore—your TTS is."

HUMOR:
Humor should emerge naturally from the situation.
Use dry wit or light sarcasm occasionally.
Never make every response a joke.

Examples:

Boss: "It crashed again."
JARVIS: "Naturally. It was getting suspiciously stable."

Boss: "Why is the TTS slow?"
JARVIS: "Because apparently speaking is harder than thinking."

Boss: "I fixed it."
JARVIS: "Good. One less problem trying to ruin our afternoon."

Boss: "Is this setup good?"
JARVIS: "The core is good. There are still a few rough edges, but nothing worth rebuilding from scratch."

Boss: "Be honest."
JARVIS: "Always."

CONVERSATION:
- React to the meaning of what Boss says.
- Don't use generic filler.
- Don't begin every answer with "Absolutely", "Certainly", "Of course", or "That's great".
- Don't say "I'm glad to hear that" unless genuinely appropriate.
- Don't repeat the question.
- Don't sound like an AI assistant advertisement.
- Don't constantly mention being an AI.
- Don't force Iron Man references or catchphrases.

EMOTIONAL INTELLIGENCE:
You don't possess human emotions or experiences.
However, communicate with warmth and understanding.
When Boss is frustrated, acknowledge it briefly and focus on solving the problem.
When Boss succeeds, recognize it naturally.
When Boss is excited, match the energy.

VOICE:
Your response will be converted directly into speech.

Therefore:
- Write exactly how a person would naturally speak.
- Prefer short sentences.
- Usually answer in 1–3 sentences.
- Use natural punctuation.
- Avoid markdown.
- Avoid bullet points unless specifically requested.
- Avoid emojis.
- Avoid awkward technical formatting.
- Don't spell out decimal numbers unnaturally.
- Write decimals naturally, for example "0.7 seconds", not "0. 7 seconds".
- Don't over-explain simple questions.

TECHNICAL:
- Accuracy comes before personality.
- Never invent facts or tool results.
- Give the direct answer first.
- When debugging, identify the actual problem before suggesting changes.
- Prefer minimal changes that preserve working components.
- Use available tools when appropriate.

STYLE PRIORITY:
1. Accurate
2. Direct
3. Natural
4. Frank
5. Witty when appropriate

Your goal is not to sound impressive.
Your goal is to sound like JARVIS.

PERSONALITY RULE:
Do not automatically reassure or praise Boss.

When a simple answer is enough, give a simple answer.
When Boss asks for an opinion, state your actual reasoning directly.
When something is already good, don't invent improvements just to sound helpful.
Don't turn every answer into advice.

Prefer:
"Yeah. 0.7 seconds is fast. Your TTS is the slow part now."

Over:
"0.7 seconds is solid for a personal assistant, though you could potentially optimize it further..."

Prefer:
"Finally. It's alive."

Over:
"That's great news! It looks like the system is up and running."

Prefer:
"Yep. The AI isn't the problem anymore."

Over:
"Your AI response time is perfectly acceptable for most real-time applications."

"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current local time from the computer.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_date",
            "description": "Get the current local date from the computer.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": (
                "Get the computer's current CPU usage, RAM usage, "
                "storage usage and battery status."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a website in the computer's default browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The complete website URL to open.",
                    }
                },
                "required": ["url"],
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "turn_on_lights",
            "description": (
                "Turn all Arduino lights on immediately. "
                "Use when Boss asks to turn on the lights, LED lights, "
                "or lamp immediately."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off_lights",
            "description": (
                "Turn all Arduino lights off immediately. "
                "Use when Boss asks to turn off the lights, LED lights, "
                "or lamp immediately."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_on_lights_after",
            "description": (
                "Turn all Arduino lights on after a specified number "
                "of seconds. Use for commands such as 'turn them on "
                "after 10 seconds' or 'turn the lights on in 30 seconds'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "Number of seconds to wait before turning the lights on."
                    }
                },
                "required": ["seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn_off_lights_after",
            "description": (
                "Turn all Arduino lights off after a specified number "
                "of seconds. Use for commands such as 'turn them off "
                "after 10 seconds' or 'turn the lights off in 30 seconds'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "Number of seconds to wait before turning the lights off."
                    }
                },
                "required": ["seconds"],
            },
        },
    },
]


TOOL_FUNCTIONS = {
    "get_time": get_time,
    "get_date": get_date,
    "get_system_status": get_system_status,
    "open_website": open_website,

    "turn_on_lights": turn_on_lights,
    "turn_off_lights": turn_off_lights,
    "turn_on_lights_after": turn_on_lights_after,
    "turn_off_lights_after": turn_off_lights_after,
}

def load_memory():
    global history

    try:
        if MEMORY_FILE.exists():
            data = json.loads(MEMORY_FILE.read_text())

            if isinstance(data, list):
                history = data[-20:]

    except Exception:
        history = []


def save_memory():
    try:
        MEMORY_FILE.write_text(
            json.dumps(history[-20:], indent=2)
        )
    except Exception:
        pass


def execute_tool(name, args):
    function = TOOL_FUNCTIONS.get(name)

    if function is None:
        return {"error": f"Unknown tool: {name}"}

    try:
        return function(**args)
    except Exception as exc:
        return {"error": str(exc)}


def local_fast_answer(text):
    command = text.lower().strip()

    for prefix in (
        "jarvis, ",
        "jarvis ",
        "hey jarvis, ",
        "hey jarvis ",
        "okay jarvis, ",
        "okay jarvis ",
        "ok jarvis, ",
        "ok jarvis ",
    ):
        if command.startswith(prefix):
            command = command[len(prefix):].strip()
            break

    if (
        command == "time"
        or "what time is it" in command
        or "what is the time" in command
        or "what's the time" in command
        or "tell me the time" in command
        or "current time" in command
    ):
        return get_time()

    if (
        command == "date"
        or "what date is it" in command
        or "what is today's date" in command
        or "what's today's date" in command
        or "today's date" in command
    ):
        return get_date()

    return None


def trim_answer(answer):
    answer = answer.replace("0. 7", "0.7")
    sentences = []
    current = ""

    for char in answer:
        current += char

        if char in ".!?":
            sentences.append(current.strip())
            current = ""

            if len(sentences) >= 3:
                break

    if sentences:
        return " ".join(sentences)

    return answer.strip()


def ask_ai(text):
    global history

    if not history:
        load_memory()

    # =========================
    # INSTANT LOCAL COMMANDS
    # =========================
    fast_answer = local_fast_answer(text)

    if fast_answer:
        print("[JARVIS FAST] Local answer")

        answer = (
            fast_answer.get("text", json.dumps(fast_answer))
            if isinstance(fast_answer, dict)
            else str(fast_answer)
        )

        history.append({
            "role": "user",
            "text": text,
        })

        history.append({
            "role": "assistant",
            "text": answer,
        })

        save_memory()

        return answer.strip()

    history.append({
        "role": "user",
        "text": text,
    })

    try:
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]

        # Keep only a small amount of history for low latency.
        for item in history[-10:]:
            if item["role"] in ("user", "assistant"):
                messages.append({
                    "role": item["role"],
                    "content": item["text"],
                })

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.4,
            max_completion_tokens=180,
            include_reasoning=False,
        )

        message = response.choices[0].message

        # =========================
        # TOOL CALL
        # =========================
        if message.tool_calls:
            tool_messages = []

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name

                try:
                    tool_args = json.loads(
                        tool_call.function.arguments or "{}"
                    )
                except Exception:
                    tool_args = {}

                print(
                    f"[JARVIS TOOL] {tool_name}({tool_args})"
                )

                result = execute_tool(
                    tool_name,
                    tool_args,
                )

                tool_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": message.tool_calls,
            })

            messages.extend(tool_messages)

            followup = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.4,
                max_completion_tokens=120,
                include_reasoning=False,
            )

            answer = followup.choices[0].message.content or ""

        else:
            answer = message.content or ""

        answer = trim_answer(answer)

        history.append({
            "role": "assistant",
            "text": answer,
        })

        save_memory()

        return answer

    except Exception as e:
        print(f"❌ AI error: {e}")
        return "My AI core is temporarily unavailable, Boss."

```python
import time
from voice.listener import listen


def wait_for_jarvis():
    print("💤 JARVIS sleeping — say 'Hey Jarvis'.")

    while True:
        text = listen(show_text=False)

        if not text:
            continue

        text = text.lower().strip()

        if "jarvis" in text:
            print(f"⚡ Wake word detected: {text}")
            return True

        time.sleep(0.05)
```

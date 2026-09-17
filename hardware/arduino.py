import serial
import time

PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600

arduino = None


def connect():
    global arduino

    try:
        arduino = serial.Serial(PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        print("🤖 Arduino connected.")
        return True

    except Exception as e:
        print(f"❌ Arduino connection failed: {e}")
        return False


def send(command):
    if arduino is None or not arduino.is_open:
        print("❌ Arduino is not connected.")
        return False

    try:
        arduino.write((command + "\n").encode())
        print(f"➡️ Arduino: {command}")
        return True

    except Exception as e:
        print(f"❌ Send failed: {e}")
        return False


def disconnect():
    global arduino

    if arduino and arduino.is_open:
        arduino.close()
        print("🔌 Arduino disconnected.")


if __name__ == "__main__":
    if connect():
        send("TEST")
        time.sleep(1)
        disconnect()

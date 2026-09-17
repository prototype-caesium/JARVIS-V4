import cv2

CAMERA_INDEX = 0


def camera_test():
    camera = cv2.VideoCapture(CAMERA_INDEX)

    if not camera.isOpened():
        print("❌ Camera could not be opened.")
        return

    print("📷 Camera started.")
    print("Press Q to quit.")

    while True:
        ret, frame = camera.read()

        if not ret:
            print("❌ Failed to read frame.")
            break

        cv2.imshow("JARVIS V4 - Camera", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()
    print("📷 Camera stopped.")


if __name__ == "__main__":
    camera_test()

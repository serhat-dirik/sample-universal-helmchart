import os
import time

uid = os.getuid()
print(f"Hello from Universal App! My container is running as UID: {uid}")
print("I will print this message every 10 seconds. Use Ctrl+C to exit.")

while True:
    print(f"Still running as UID: {uid}...")
    time.sleep(10)
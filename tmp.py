import threading
import time

def worker():
    for i in range(5):
        print("Worker")
        time.sleep(1)

thread = threading.Thread(target=worker)

thread.start()
thread.join()

print("Main thread")
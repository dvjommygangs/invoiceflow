import pyngrok.ngrok as ngrok
import time

url = ngrok.connect(5000)
print(f"PUBLIC_URL={url}")

while True:
    time.sleep(1)

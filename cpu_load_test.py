
import concurrent.futures
import time
import urllib.request

URL = "http://127.0.0.1:8091/"
WORKERS = 10
DURATION_SECONDS = 120
TIMEOUT_SECONDS = 5

stop_at = time.monotonic() + DURATION_SECONDS
success = 0
failed = 0


def request_page():
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT_SECONDS) as response:
            response.read()

        # Deliberately consume CPU on the client to sustain
        # HTTP traffic. This does NOT guarantee high CPU inside
        # the Nginx container.
        value = 0
        for number in range(100_000):
            value = (value + number * number) % 1_000_003

        return True
    except Exception:
        return False


print(f"Testing {URL}")
print(f"Workers: {WORKERS}; duration: {DURATION_SECONDS}s")
print("Press Ctrl+C to stop early.")

try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        while time.monotonic() < stop_at:
            futures = [pool.submit(request_page) for _ in range(WORKERS)]
            for future in futures:
                if future.result():
                    success += 1
                else:
                    failed += 1
            print(
                f"\rSuccessful: {success} | Failed: {failed}",
                end="",
                flush=True,
            )
except KeyboardInterrupt:
    print("\nStopped by user.")

print(f"\nFinished. Successful: {success}; failed: {failed}")


import concurrent.futures
import time
import urllib.request

URL = "http://127.0.0.1:8091/"
WORKERS = 10
DURATION_SECONDS = 90
TIMEOUT_SECONDS = 3

stop_at = time.monotonic() + DURATION_SECONDS
success = 0
failed = 0


def request_page():
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT_SECONDS) as response:
            response.read()
            return response.status == 200
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
            print(f"\rSuccessful: {success} | Failed: {failed}", end="", flush=True)
except KeyboardInterrupt:
    print("\nStopped by user.")

print(f"\nFinished. Successful: {success}; failed: {failed}")

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPOSE = ROOT / "compose_projects" / "dockpilot-scaled-demo" / "compose.yaml"
PROJECT = "dockpilot-scaled-demo"
SERVICE = "web"


def scale(replicas):
    result = subprocess.run(
        [
            "docker", "compose",
            "-p", PROJECT,
            "-f", str(COMPOSE),
            "up", "-d",
            "--scale", f"{SERVICE}={replicas}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )

    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise SystemExit(result.returncode)


def show():
    subprocess.run(
        [
            "docker", "compose",
            "-p", PROJECT,
            "-f", str(COMPOSE),
            "ps",
        ],
        check=False,
    )


try:
    print("TEST 1: Scaling web from 1 to 2 replicas")
    scale(2)
    show()

    input("\nVerify that two web replicas are running. Press Enter to restore one replica...")

finally:
    print("\nRestoring web service to one replica...")
    scale(1)
    show()
    print("Test complete. Original replica count restored.")
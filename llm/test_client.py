import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

from llm import generate

if __name__ == "__main__":
    result = generate("Say hello in Hindi")
    print(f"\nEngine : {result.engine}")
    print(f"Answer : {result.text}")

import logging
import sys
import os


def setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric)

    # Quiet noisy third-party libs by default
    quiet_libs = os.getenv("QUIET_LIBS", "true").lower() == "true"
    lib_level_str = os.getenv("LIB_LOG_LEVEL", "WARNING").upper()
    lib_level = getattr(logging, lib_level_str, logging.WARNING)
    if quiet_libs:
        for name in ("telethon", "httpx", "httpcore", "asyncio"):
            logging.getLogger(name).setLevel(lib_level)


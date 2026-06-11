#!/usr/bin/env python3
import os
import sys
import time

mode = os.environ.get("FAKE_MODE", "pass")

if mode == "pass":
    print("fake harness: success")
    sys.exit(0)
elif mode == "fail":
    print("fake harness: failure", file=sys.stderr)
    sys.exit(1)
elif mode == "hang":
    time.sleep(9999)
    sys.exit(0)
else:
    print(f"unknown FAKE_MODE: {mode!r}", file=sys.stderr)
    sys.exit(2)

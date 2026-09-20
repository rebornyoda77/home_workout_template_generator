#!/usr/bin/env python3
"""Standalone entry point for the Flask web interface.

Usage:
    python web_main.py --set-passcode   # set (or change) the web passcode
    python web_main.py                  # run the server (default 127.0.0.1:5050)
"""

import argparse
import getpass
import sys

from workout_generator import web_config, web_server


def _set_passcode() -> None:
    passcode = getpass.getpass("New web passcode: ")
    if not passcode:
        print("Passcode cannot be blank.", file=sys.stderr)
        sys.exit(1)
    confirm = getpass.getpass("Confirm: ")
    if passcode != confirm:
        print("Passcodes didn't match.", file=sys.stderr)
        sys.exit(1)
    web_config.set_web_passcode(passcode)
    print("Web passcode set.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the workout generator's web interface.")
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Interface to bind to (default: 127.0.0.1 -- use a tool like tailscale serve "
             "rather than binding 0.0.0.0 directly if you want it reachable from other devices).",
    )
    parser.add_argument(
        "--port", type=int, default=web_server.DEFAULT_PORT,
        help=f"Port to listen on (default: {web_server.DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--set-passcode", action="store_true",
        help="Set (or change) the web passcode interactively, then exit -- doesn't start the server.",
    )
    args = parser.parse_args()

    if args.set_passcode:
        _set_passcode()
        return

    if not web_config.has_web_passcode():
        print(
            "No web passcode is set yet. Set one first with:\n\n"
            "    python web_main.py --set-passcode\n",
            file=sys.stderr,
        )
        sys.exit(1)

    app = web_server.create_app()
    print(f"Workout Generator web interface running at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()

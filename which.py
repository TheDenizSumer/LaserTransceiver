"""
Wrapper entrypoint for the project frontend.

This exists because the UI implementation lives in `frontend.py`, but some
workflows may expect the script to be named `which.py`.
"""

from frontend import LaserTransceiverFrontend


def main() -> None:
    app = LaserTransceiverFrontend()
    app.run()


if __name__ == "__main__":
    main()


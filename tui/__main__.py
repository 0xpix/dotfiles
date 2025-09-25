from . import main as main_mod
import curses, sys


def _entry():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("tui: not a TTY (run in a real terminal)")
        return
    try:
        curses.wrapper(main_mod.main)
    except Exception as e:
        # Provide a fallback error so failures aren't silent
        print(f"tui crashed: {e}")
        raise

if __name__ == "__main__":
    _entry()

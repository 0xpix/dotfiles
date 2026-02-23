
# Minimal TUI for dotfiles management

import curses, os, subprocess, pathlib, shlex, threading, time, queue, shutil
from .ops import load_config, ensure_packages, clone_repos, package_plan

ROOT = pathlib.Path(__file__).resolve().parent.parent
STOW_DIR = ROOT / "stow"

# UI event queue (all curses drawing must happen on main thread)
ui_events = queue.Queue()

# Icons
ICONS = {"info": "·", "success": "✓", "warn": "!", "error": "✗"}
HINT_MENU = "↑/↓ navigate  ⏎ select  ? help  q quit"
HINT_PAGE = "␣ toggle  ⏎ run  a/u all/none  / filter  ? help  b back"

# Color pairs (will be initialized if colors available)
COLORS = {}

def init_colors():
    """Initialize muted color pairs for a minimal look"""
    global COLORS
    if not curses.has_colors():
        return

    curses.start_color()
    try:
        curses.init_pair(1, curses.COLOR_WHITE, -1)                  # title
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)   # cursor
        curses.init_pair(3, curses.COLOR_GREEN, -1)                  # success/selected
        curses.init_pair(4, curses.COLOR_YELLOW, -1)                 # warning
        curses.init_pair(5, curses.COLOR_RED, -1)                    # error
        curses.init_pair(6, curses.COLOR_CYAN, -1)                   # info/accent
        curses.init_pair(7, curses.COLOR_WHITE, -1)                  # status bar

        COLORS = {
            'title': curses.color_pair(1) | curses.A_BOLD,
            'cursor': curses.color_pair(2) | curses.A_BOLD,
            'accent': curses.color_pair(6) | curses.A_BOLD,
            'success': curses.color_pair(3),
            'warn': curses.color_pair(4),
            'error': curses.color_pair(5),
            'info': curses.color_pair(6),
            'dim': curses.A_DIM,
            'status': curses.color_pair(7) | curses.A_DIM
        }
    except curses.error:
        pass

def list_packages():
    """List available stow packages"""
    if not STOW_DIR.exists():
        return []
    return sorted([p.name for p in STOW_DIR.iterdir() if p.is_dir()])

def inside_home_guard(path: pathlib.Path) -> bool:
    """Return True iff path is lexically under $HOME (no traversal above HOME).
    This guard does NOT follow symlinks; use additional checks for recursive deletes.
    """
    try:
        home = pathlib.Path(os.path.expanduser("~")).absolute()
        p = pathlib.Path(path).expanduser().absolute()
        return p.is_relative_to(home)
    except Exception:
        return False

def enumerate_stow_targets_for_pkgs(pkgs) -> tuple[list[str], list[str]]:
    """Walk stow/<pkg> trees and return (files, dirs) as HOME-absolute target paths,
    exactly mirroring Stow mapping with -t "$HOME". Skip .git folders. De-duplicate and sort.
    """
    home = pathlib.Path(os.path.expanduser("~"))
    files: set[str] = set()
    dirs: set[str] = set()

    for pkg in sorted(set(pkgs)):
        pkg_dir = STOW_DIR / pkg
        if not pkg_dir.exists() or not pkg_dir.is_dir():
            continue
        # Walk without following symlinks
        for root, dnames, fnames in os.walk(pkg_dir, topdown=True, followlinks=False):
            # Skip VCS dirs
            dnames[:] = [d for d in dnames if d != ".git"]
            root_path = pathlib.Path(root)
            rel_root = root_path.relative_to(pkg_dir)
            # Add directories (excluding the package root itself)
            if str(rel_root) != ".":
                target_dir = home / rel_root
                if inside_home_guard(target_dir):
                    dirs.add(str(target_dir))
            # Add subdirectories explicitly as targets too
            for d in dnames:
                rel_dir = (rel_root / d)
                if str(rel_dir) == ".":
                    continue
                target_dir = home / rel_dir
                if inside_home_guard(target_dir):
                    dirs.add(str(target_dir))
            # Add files (regular or symlink) -> treated as file targets
            for f in fnames:
                rel_file = (rel_root / f)
                target_file = home / rel_file
                if inside_home_guard(target_file):
                    files.add(str(target_file))

    # De-duplicate and sort; ensure deterministic order
    files_list = sorted(files)
    # For directory deletion, remove deeper ones first later; but here just sort
    dirs_list = sorted(dirs)
    return files_list, dirs_list

def confirm_remove_dialog(stdscr, paths: list[str]) -> bool:
    """Centered modal listing planned removals. Ask user to type the exact count to confirm. ESC cancels."""
    total = len(paths)
    h, w = stdscr.getmaxyx()
    box_w = min(80, w - 4)
    # Leave space for header, footer, input
    max_list_lines = max(5, min(18, h - 10))
    visible = paths[:max_list_lines]
    more = total - len(visible)

    # Draw loop (simple, static list; input at bottom)
    box_h = 8 + len(visible) + (1 if more > 0 else 0)
    start_x, start_y = (w - box_w) // 2, (h - box_h) // 2

    typed = ""
    curses.curs_set(1)
    try:
        while True:
            # Clear area
            for y in range(start_y, start_y + box_h):
                try:
                    stdscr.addstr(y, start_x, " " * box_w, curses.A_REVERSE)
                except curses.error:
                    pass
            # Border
            try:
                stdscr.addstr(start_y, start_x, "+" + "-" * (box_w - 2) + "+", curses.A_REVERSE)
                for y in range(start_y + 1, start_y + box_h - 1):
                    stdscr.addstr(y, start_x, "|", curses.A_REVERSE)
                    stdscr.addstr(y, start_x + box_w - 1, "|", curses.A_REVERSE)
                stdscr.addstr(start_y + box_h - 1, start_x, "+" + "-" * (box_w - 2) + "+", curses.A_REVERSE)
            except curses.error:
                pass

            title = f"Selective Cleanup: {total} item(s) will be removed"
            hint = f"Type {total} to confirm, Esc to cancel"
            try:
                stdscr.addstr(start_y + 1, start_x + 2, title[:box_w-4], curses.A_REVERSE | curses.A_BOLD)
            except curses.error:
                pass

            list_y = start_y + 3
            for i, p in enumerate(visible):
                line = ("~" + str(pathlib.Path(p).expanduser()).replace(str(pathlib.Path.home()), "")) if p.startswith(str(pathlib.Path.home())) else p
                try:
                    stdscr.addstr(list_y + i, start_x + 2, f"- {line}"[:box_w-4], curses.A_REVERSE)
                except curses.error:
                    pass
            if more > 0:
                try:
                    stdscr.addstr(list_y + len(visible), start_x + 2, f"... and {more} more"[:box_w-4], curses.A_REVERSE | curses.A_DIM)
                except curses.error:
                    pass

            input_y = start_y + box_h - 3
            try:
                stdscr.addstr(input_y, start_x + 2, hint[:box_w-4], curses.A_REVERSE)
                stdscr.addstr(input_y + 1, start_x + 2, ("Confirm count: " + typed)[:box_w-4], curses.A_REVERSE)
                stdscr.move(input_y + 1, start_x + 2 + len("Confirm count: ") + len(typed))
                stdscr.refresh()
            except curses.error:
                pass

            key = stdscr.getch()
            if key in (27,):  # ESC
                return False
            elif key in (10, 13):  # Enter => accept if matches
                try:
                    if int(typed) == total:
                        return True
                except Exception:
                    pass
                return False
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                if typed:
                    typed = typed[:-1]
            elif 48 <= key <= 57:  # digits
                if len(typed) < 10:
                    typed += chr(key)
            else:
                # ignore others
                pass
    finally:
        try:
            curses.curs_set(0)
        except curses.error:
            pass

def selective_cleanup_worker(files: list[str], dirs: list[str], logger):
    """Headless worker performing selective cleanup.
      - If DOTFILES_REMOVE_DRY: log actions only.
      - Remove files/symlinks via unlink; log each.
      - Remove dirs: default rmdir if empty; if DOTFILES_REMOVE_FORCE: rmtree.
      - Return summary dict: {'files_removed': n1, 'dirs_removed': n2, 'skipped': k, 'errors': e, 'dry_run': bool}
    """
    dry = os.getenv("DOTFILES_REMOVE_DRY", "0") in ("1", "true", "yes", "on")
    force = os.getenv("DOTFILES_REMOVE_FORCE", "0") in ("1", "true", "yes", "on")

    files_removed = 0
    dirs_removed = 0
    skipped = 0
    errors = 0

    home = pathlib.Path(os.path.expanduser("~")).absolute()

    # Remove files and symlinks first
    logger("info", f"Planned removals: {len(files)} file(s)/link(s), {len(dirs)} dir(s)" + (" [DRY RUN]" if dry else ""))

    for f in files:
        try:
            p = pathlib.Path(f)
            if not inside_home_guard(p):
                logger("warn", f"skip: outside $HOME (guard): {f}")
                skipped += 1
                continue
            if not p.exists() and not p.is_symlink():
                logger("info", f"skip: not found: {f}")
                skipped += 1
                continue
            # We never follow symlinks for file targets; unlink() handles both
            if dry:
                kind = "symlink" if p.is_symlink() else ("file" if p.exists() else "file/symlink")
                logger("info", f"plan: unlink {kind}: {f}")
                continue
            try:
                p.unlink(missing_ok=True)
                logger("success", f"removed: {f}")
                files_removed += 1
            except Exception as e:
                logger("error", f"failed to remove file/link: {f}: {e}")
                errors += 1
        except Exception as e:
            logger("error", f"error processing file: {f}: {e}")
            errors += 1

    # Then directories; attempt to remove deepest first to handle nesting
    # Sort by depth descending
    dirs_sorted = sorted(dirs, key=lambda s: s.count(os.sep), reverse=True)

    for d in dirs_sorted:
        try:
            p = pathlib.Path(d)
            if not inside_home_guard(p):
                logger("warn", f"skip dir: outside $HOME (guard): {d}")
                skipped += 1
                continue
            if not p.exists() and not p.is_symlink():
                logger("info", f"skip dir: not found: {d}")
                skipped += 1
                continue
            # If target is a file or symlink, treat like file unlink attempt
            if p.is_file() or p.is_symlink():
                if dry:
                    logger("info", f"plan: unlink file/symlink for dir target: {d}")
                    continue
                try:
                    p.unlink(missing_ok=True)
                    logger("success", f"removed file/symlink for dir target: {d}")
                    files_removed += 1
                except Exception as e:
                    logger("error", f"failed to unlink for dir target: {d}: {e}")
                    errors += 1
                continue

            # It's a directory at this point
            if dry:
                action = "rmtree" if force else "rmdir (if empty)"
                logger("info", f"plan: {action}: {d}")
                continue

            # Extra safety for recursive deletes: ensure resolved path under HOME and not a symlink
            if force:
                try:
                    if p.is_symlink():
                        # Do not rmtree symlink dirs; just unlink
                        p.unlink(missing_ok=True)
                        logger("success", f"removed symlink dir: {d}")
                        files_removed += 1
                    else:
                        resolved = p.resolve()
                        if not resolved.is_relative_to(home):
                            logger("error", f"refuse rmtree outside $HOME after resolve: {d}")
                            errors += 1
                        else:
                            shutil.rmtree(p)
                            logger("success", f"removed dir (recursive): {d}")
                            dirs_removed += 1
                except Exception as e:
                    logger("error", f"failed to remove dir recursively: {d}: {e}")
                    errors += 1
            else:
                try:
                    os.rmdir(p)
                    logger("success", f"removed dir (empty): {d}")
                    dirs_removed += 1
                except OSError as e:
                    if getattr(e, 'errno', None) == 39 or 'Directory not empty' in str(e):
                        logger("info", f"skip dir not empty: {d} (set DOTFILES_REMOVE_FORCE=1 to force)")
                        skipped += 1
                    else:
                        logger("error", f"failed to rmdir: {d}: {e}")
                        errors += 1
                except Exception as e:
                    logger("error", f"failed to rmdir: {d}: {e}")
                    errors += 1

        except Exception as e:
            logger("error", f"error processing dir: {d}: {e}")
            errors += 1

    return {
        'files_removed': files_removed,
        'dirs_removed': dirs_removed,
        'skipped': skipped,
        'errors': errors,
        'dry_run': dry,
    }

# -----------------------------
# Themes discovery and copying
# -----------------------------
def theme_sources() -> list[pathlib.Path]:
    """Return ordered list of existing source dirs for themes.
    Env override DOTFILES_THEMES_SRC=path1:path2 (relative paths resolved against repo ROOT).
    Default order (earlier preferred): ./themes, ./assets/themes, ./stow/omarchy/.config/omarchy/themes
    """
    env = os.getenv("DOTFILES_THEMES_SRC")
    sources: list[pathlib.Path] = []
    if env:
        for raw in env.split(":" ):
            if not raw:
                continue
            p = pathlib.Path(raw)
            if not p.is_absolute():
                p = (ROOT / p)
            p = p.expanduser()
            try:
                p = p.resolve()
            except Exception:
                p = p.absolute()
            if p.exists() and p.is_dir():
                sources.append(p)
        return sources

    defaults = [
        ROOT / "themes",
        ROOT / "assets" / "themes",
        ROOT / "stow" / "omarchy" / ".config" / "omarchy" / "themes",
    ]
    for d in defaults:
        try:
            if d.exists() and d.is_dir():
                sources.append(d.resolve())
        except Exception:
            pass
    return sources

def discover_themes() -> dict[str, pathlib.Path]:
    """Return {theme_name: source_path}. Prefer earlier sources on name conflicts.
    - theme_name: folder name or file stem.
    - source_path: absolute path to the folder or file in the repo.
    Includes top-level files with extensions: .json, .toml, .ini, .css
    """
    exts = {".json", ".toml", ".ini", ".css"}
    result: dict[str, pathlib.Path] = {}
    for src_dir in theme_sources():
        try:
            for entry in sorted(src_dir.iterdir(), key=lambda p: p.name.lower()):
                name = None
                if entry.name == ".git":
                    continue
                if entry.is_dir():
                    name = entry.name
                elif entry.is_file() and entry.suffix.lower() in exts:
                    name = entry.stem
                if not name:
                    continue
                if name not in result:
                    try:
                        result[name] = entry.resolve()
                    except Exception:
                        result[name] = entry.absolute()
        except Exception:
            # Skip unreadable source directories
            continue
    return result

def ensure_dest() -> pathlib.Path:
    """Create and return Path('~/.config/omarchy/themes').expanduser().resolve()"""
    home = pathlib.Path(os.path.expanduser("~"))
    dest = (home / ".config" / "omarchy" / "themes").expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        dest = dest.resolve()
    except Exception:
        dest = dest.absolute()
    return dest

def _safe_remove_target(target: pathlib.Path, logger):
    """Remove target path safely (file/symlink or directory). Do not follow symlinks."""
    try:
        if target.is_symlink() or target.is_file():
            target.unlink(missing_ok=True)
            logger("success", f"removed existing: {target}")
        elif target.exists() and target.is_dir():
            # Ensure not a symlinked dir
            try:
                if target.is_symlink():
                    target.unlink(missing_ok=True)
                    logger("success", f"removed symlink: {target}")
                else:
                    shutil.rmtree(target)
                    logger("success", f"removed directory: {target}")
            except Exception as e:
                logger("error", f"failed removing {target}: {e}")
                raise
    except Exception as e:
        logger("error", f"failed to remove {target}: {e}")
        raise

def copy_theme(src: pathlib.Path, dst_root: pathlib.Path, force: bool, logger) -> tuple[bool, str]:
    """Copy one theme (folder or file) to dst_root/<name>.
    - If force: remove existing target (file or dir) first (unlink or rmtree).
    - Else: merge directories, overwrite files.
    - Return (ok, theme_name); log steps and errors.
    """
    src = src.expanduser()
    try:
        src_resolved = src.resolve()
    except Exception:
        src_resolved = src.absolute()
    name = src_resolved.name if src_resolved.is_dir() else src_resolved.stem

    # Compute destination target path
    if src_resolved.is_file():
        dst_target = dst_root / src_resolved.name  # keep extension
    else:
        dst_target = dst_root / name

    # Guard destination path
    try:
        dst_root_res = dst_root.resolve()
        dst_target_res = dst_target.resolve() if dst_target.exists() else dst_target
        if not dst_target_res.absolute().is_relative_to(dst_root_res):
            logger("error", f"refuse to write outside destination: {dst_target}")
            return False, name
    except Exception:
        pass

    # Force remove if requested
    if force and (dst_target.exists() or dst_target.is_symlink()):
        logger("info", f"force remove existing target: {dst_target}")
        _safe_remove_target(dst_target, logger)

    # Copy
    try:
        if src_resolved.is_file():
            dst_root.mkdir(parents=True, exist_ok=True)
            logger("info", f"copy file: {src_resolved} -> {dst_target}")
            shutil.copy2(src_resolved, dst_target)
        elif src_resolved.is_dir():
            # Merge copy (create dirs, overwrite files)
            for root, dnames, fnames in os.walk(src_resolved, topdown=True, followlinks=False):
                # Skip .git
                dnames[:] = [d for d in dnames if d != ".git"]
                rel_root = pathlib.Path(root).relative_to(src_resolved)
                out_dir = dst_target / rel_root
                out_dir.mkdir(parents=True, exist_ok=True)
                for f in fnames:
                    s_file = pathlib.Path(root) / f
                    d_file = out_dir / f
                    logger("info", f"copy: {s_file} -> {d_file}")
                    shutil.copy2(s_file, d_file)
        else:
            logger("warn", f"skip: not a regular file or directory: {src_resolved}")
            return False, name
        logger("success", f"copied theme: {name}")
        return True, name
    except Exception as e:
        logger("error", f"failed copy for theme {name}: {e}")
        return False, name

def copy_themes_worker(selected_names: list[str], logger) -> dict:
    """Copy multiple themes.
    Respects DOTFILES_THEMES_DRY and DOTFILES_THEMES_FORCE.
    Returns summary dict.
    """
    dry = os.getenv("DOTFILES_THEMES_DRY", "0") in ("1", "true", "yes", "on")
    force = os.getenv("DOTFILES_THEMES_FORCE", "0") in ("1", "true", "yes", "on")

    themes = discover_themes()
    dest = ensure_dest()

    ok = 0
    skipped = 0
    errors = 0

    logger("info", f"Copying {len(selected_names)} theme(s) to {dest}" + (" [DRY RUN]" if dry else ""))
    for name in selected_names:
        src = themes.get(name)
        if not src:
            logger("warn", f"skip: source not found for theme '{name}'")
            skipped += 1
            continue
        if dry:
            # Compute planned destination
            target = (dest / (src.name if src.is_file() else name))
            logger("info", f"plan: copy {src} -> {target}" + (" (force replace)" if force else ""))
            continue
        try:
            ok_single, _ = copy_theme(src, dest, force, logger)
            if ok_single:
                ok += 1
            else:
                errors += 1
        except Exception as e:
            logger("error", f"exception copying '{name}': {e}")
            errors += 1

    return {"ok": ok, "skipped": skipped, "errors": errors, "dry": dry}

def check_stow():
    """Check if stow is installed"""
    return subprocess.call("command -v stow >/dev/null 2>&1", shell=True) == 0

def run(cmd, logger, cwd=None):
    """Run command and stream output to logger"""
    logger("cmd", f"{cmd}")
    p = subprocess.Popen(
        cmd, shell=True, cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1,
        env={**os.environ, "HOME": os.path.expanduser("~")}
    )
    for line in p.stdout or []:
        logger("info", line.rstrip("\n"))
    p.wait()

    if p.returncode == 0:
        logger("success", f"Command completed successfully")
    else:
        logger("error", f"Command failed with exit code {p.returncode}")

    return p.returncode

class LogBuf:
    """Ring buffer for log messages with levels and auto-follow"""
    def __init__(self, cap=5000):
        self.lines = []
        self.cap = cap
        self.scroll = 0
        self.follow = True
        self.dirty = True  # mark when content changes

    def add(self, level, msg):
        icon = ICONS.get(level, "•")
        self.lines.append(f"{icon} {msg}")
        if len(self.lines) > self.cap:
            self.lines = self.lines[-self.cap:]
        if self.follow:
            self.scroll = 0
        self.dirty = True

    def clear(self):
        self.lines.clear()
        self.scroll = 0
        self.follow = True
        self.dirty = True

def clear_rect(win, y, x, h, w):
    """Clear a rectangle"""
    for row in range(h):
        if y + row >= 0:
            try:
                win.move(y + row, x)
                win.clrtoeol()
            except curses.error:
                pass

def draw_line(win, y, x, w, label=None):
    """Draw a thin horizontal divider with optional label"""
    if w < 2:
        return
    try:
        line = '─' * w
        if label:
            tag = f" {label} "
            if len(tag) < w - 4:
                line = '──' + tag + '─' * (w - 2 - len(tag))
        win.addstr(y, x, line[:w], curses.A_DIM)
    except curses.error:
        pass

# Keep draw_box as alias for compatibility with confirm_remove_dialog
def draw_box(win, y, x, h, w, title=None):
    """Simple box for dialogs only"""
    if h < 2 or w < 2:
        return
    try:
        win.addch(y, x, ord('┌'))
        win.hline(y, x + 1, ord('─'), w - 2)
        win.addch(y, x + w - 1, ord('┐'))
        for i in range(1, h - 1):
            win.addch(y + i, x, ord('│'))
            win.addch(y + i, x + w - 1, ord('│'))
        win.addch(y + h - 1, x, ord('└'))
        win.hline(y + h - 1, x + 1, ord('─'), w - 2)
        win.addch(y + h - 1, x + w - 1, ord('┘'))
        if title and len(title) < w - 4:
            win.addstr(y, x + 2, f" {title} ")
    except curses.error:
        pass

def toast(stdscr, title, lines, is_error=False):
    """Show a minimal centered overlay"""
    H, W = stdscr.getmaxyx()
    max_w = min(W - 6, 50)
    content_lines = lines[:6]
    box_h = len(content_lines) + 4
    box_w = max(len(title) + 6, max_w)
    box_w = min(box_w, W - 2)

    sy = (H - box_h) // 2
    sx = (W - box_w) // 2

    try:
        for y in range(box_h):
            stdscr.addstr(sy + y, sx, ' ' * box_w, curses.A_REVERSE)
        stdscr.addstr(sy + 1, sx + 2, title[:box_w - 4], curses.A_REVERSE | curses.A_BOLD)
        for i, line in enumerate(content_lines):
            stdscr.addstr(sy + 2 + i, sx + 2, line[:box_w - 4], curses.A_REVERSE)
        stdscr.addstr(sy + box_h - 1, sx + 2, "press any key", curses.A_REVERSE | curses.A_DIM)
    except curses.error:
        pass

    stdscr.refresh()

def password_dialog(stdscr, title="Enter sudo password:"):
    """Show a password input dialog using overlay approach."""
    h, w = stdscr.getmaxyx()
    box_w, box_h = min(50, w - 4), 7
    start_x, start_y = (w - box_w) // 2, (h - box_h) // 2

    password = ""
    max_password_len = box_w - 14

    # Store original screen content to restore later
    try:
        # Create a simple overlay approach - draw directly on main screen but save/restore
        original_cursor = curses.curs_set(1)  # Show cursor

        def draw_dialog():
            """Draw dialog as overlay on main screen"""
            try:
                # Clear dialog area with solid background
                for y in range(start_y, start_y + box_h):
                    stdscr.addstr(y, start_x, " " * box_w, curses.A_REVERSE)

                # Draw simple box using basic characters (more compatible)
                stdscr.addstr(start_y, start_x, "+" + "-" * (box_w - 2) + "+", curses.A_REVERSE)
                for y in range(start_y + 1, start_y + box_h - 1):
                    stdscr.addstr(y, start_x, "|", curses.A_REVERSE)
                    stdscr.addstr(y, start_x + box_w - 1, "|", curses.A_REVERSE)
                stdscr.addstr(start_y + box_h - 1, start_x, "+" + "-" * (box_w - 2) + "+", curses.A_REVERSE)

                # Content with high contrast
                title_y = start_y + 1
                input_y = start_y + 3
                help_y = start_y + 5

                # Title
                stdscr.addstr(title_y, start_x + 2, title[:box_w-4], curses.A_REVERSE | curses.A_BOLD)

                # Password field
                stdscr.addstr(input_y, start_x + 2, "Password:", curses.A_REVERSE)

                # Show password as stars
                if password:
                    mask = "*" * len(password)
                    stdscr.addstr(input_y, start_x + 12, mask, curses.A_REVERSE)

                # Clear any extra chars in password field
                remaining_space = max_password_len - len(password)
                if remaining_space > 0:
                    stdscr.addstr(input_y, start_x + 12 + len(password), " " * remaining_space, curses.A_REVERSE)

                # Instructions
                help_text = "Enter=OK, Esc=Cancel"[:box_w-4]
                stdscr.addstr(help_y, start_x + 2, help_text, curses.A_REVERSE)

                # Position cursor
                stdscr.move(input_y, start_x + 12 + len(password))
                stdscr.refresh()

            except curses.error:
                pass  # Ignore positioning errors

        # Initial draw
        draw_dialog()

        # Input loop
        while True:
            try:
                key = stdscr.getch()

                if key == 27:  # Esc - cancel
                    curses.curs_set(original_cursor)
                    return None
                elif key in (10, 13):  # Enter - confirm
                    curses.curs_set(original_cursor)
                    return password
                elif key in (8, 127, curses.KEY_BACKSPACE):  # Backspace
                    if password:
                        password = password[:-1]
                        draw_dialog()
                elif 32 <= key <= 126:  # Printable characters
                    if len(password) < max_password_len:
                        password += chr(key)
                        draw_dialog()

            except curses.error:
                continue

    except Exception:
        # Ensure cursor is restored even on error
        try:
            curses.curs_set(original_cursor)
        except:
            pass
        return None

def ensure_sudo_cached_on_main(stdscr, logger) -> bool:
    """Ensure sudo credential timestamp is cached (main thread only).
    Returns True if sudo available, False if user cancelled or auth failed.
    """
    try:
        if os.geteuid() == 0:
            return True
        # Non-interactive check first
        if subprocess.call("sudo -n true", shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            return True
        pwd = password_dialog(stdscr, "Enter sudo password:")
        if pwd is None:
            logger("info", "Cancelled by user")
            return False
        p = subprocess.run("sudo -S -v", shell=True, text=True,
                           input=pwd + "\n",
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if p.returncode != 0:
            logger("error", "Invalid sudo password")
            return False
        logger("success", "Sudo authenticated")
        return True
    except Exception as e:
        logger("error", f"Failed to authenticate sudo: {e}")
        return False

def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(100)  # Non-blocking-ish getch for periodic UI ticks
    try:
        curses.use_default_colors()
    except curses.error:
        pass

    init_colors()

    # Load configuration and data
    cfg = load_config()
    stow_pkgs = list_packages()
    sys_pkgs = package_plan(cfg)
    plugin_repos = [r for r in cfg.get("repos", []) if "/.oh-my-zsh/custom/plugins/" in r.get("dest", "")]
    plugins = [r["dest"].split("/.oh-my-zsh/custom/plugins/")[-1] for r in plugin_repos]

    # UI state
    panes = ["Stow Packages", "Themes", "System Packages", "Plugins"]
    current_pane = 0
    idx = 0
    view = "menu"   # "menu" = home screen, "page" = category detail
    menu_idx = 0

    # Selection state for each pane
    selected_stow = set(stow_pkgs)
    themes_map = discover_themes()
    theme_names = sorted(themes_map.keys())
    selected_themes = set(theme_names)
    selected_pkgs = set(sys_pkgs)
    selected_plugins = set(plugins)

    # Filter state
    filter_text = ""
    filtered_stow = stow_pkgs[:]
    filtered_themes = theme_names[:]
    filtered_pkgs = sys_pkgs[:]
    filtered_plugins = plugins[:]

    log = LogBuf()
    is_running = False
    running_label = None
    show_help = False
    action_thread = None
    last_draw = 0.0
    last_spinner_frame = -1
    last_log_redraw_time = 0.0
    LOG_REDRAW_INTERVAL = 0.15
    suppress_enter_once = False

    def logger(level, msg):
        # Headless logger: only mutates buffer; draw happens in main loop tick
        log.add(level, msg)

    def get_current_data():
        """Get current pane's data (items, selected, filtered)"""
        if current_pane == 0:
            return stow_pkgs, selected_stow, filtered_stow
        elif current_pane == 1:
            return theme_names, selected_themes, filtered_themes
        elif current_pane == 2:
            return sys_pkgs, selected_pkgs, filtered_pkgs
        else:
            return plugins, selected_plugins, filtered_plugins

    def apply_filter():
        """Apply current filter to all panes"""
        nonlocal filtered_stow, filtered_themes, filtered_pkgs, filtered_plugins, idx

        if not filter_text:
            filtered_stow = stow_pkgs[:]
            filtered_themes = theme_names[:]
            filtered_pkgs = sys_pkgs[:]
            filtered_plugins = plugins[:]
        else:
            ft = filter_text.lower()
            filtered_stow = [p for p in stow_pkgs if ft in p.lower()]
            filtered_themes = [t for t in theme_names if ft in t.lower()]
            filtered_pkgs = [p for p in sys_pkgs if ft in p.lower()]
            filtered_plugins = [p for p in plugins if ft in p.lower()]

        # Adjust index for current pane
        _, _, current_filtered = get_current_data()
        idx = min(idx, max(0, len(current_filtered) - 1))

    def draw(partial: bool = False):
        """Draw minimal UI — either menu or page view."""
        nonlocal show_help, last_draw, last_spinner_frame
        H, W = stdscr.getmaxyx()

        if H < 10 or W < 30:
            stdscr.clear()
            try:
                stdscr.addstr(H // 2, max(0, (W - 10) // 2), "Too small", curses.A_DIM)
            except curses.error:
                pass
            stdscr.refresh()
            return

        if not partial:
            stdscr.clear()

        if view == "menu":
            _draw_menu(stdscr, H, W)
        else:
            _draw_page(stdscr, H, W, partial)

        # ── Help overlay ──
        if show_help:
            if view == "menu":
                help_lines = [
                    "↑/↓ k/j  navigate",
                    "⏎        open page",
                    "q        quit",
                ]
            else:
                help_lines = [
                    "↑/↓ k/j  navigate       ␣  toggle select",
                    "a  all    u  none        i  invert",
                    "⏎  run    /  filter      r  refresh",
                    "D  cleanup (stow page)   c  clear log",
                    "b  back to menu",
                ]
            toast(stdscr, "Keys", help_lines)

        stdscr.refresh()
        last_draw = time.time()
        log.dirty = False

    def _draw_menu(stdscr, H, W):
        """Draw centered home screen with button list."""
        # Title centered near top third
        title = "dotfiles"
        title_attr = COLORS.get('title', curses.A_BOLD)
        title_y = max(1, H // 4 - 2)
        try:
            stdscr.addstr(title_y, (W - len(title)) // 2, title, title_attr)
        except curses.error:
            pass

        # Buttons
        btn_width = max(len(p) for p in panes) + 6  # padding inside button
        start_y = title_y + 3
        for i, pane in enumerate(panes):
            is_cur = i == menu_idx
            label = pane.center(btn_width)
            x = (W - btn_width) // 2

            if is_cur:
                # Highlighted button: reverse video
                attr = COLORS.get('cursor', curses.A_REVERSE)
                prefix = "▸ "
            else:
                attr = curses.A_DIM
                prefix = "  "

            full = f"{prefix}{label}"
            try:
                stdscr.addstr(start_y + i * 2, max(0, x - 2), full[:W - 2], attr)
            except curses.error:
                pass

        # Hint bar at bottom
        status_y = H - 1
        try:
            stdscr.addstr(status_y, 0, f"  {HINT_MENU}"[:W].ljust(W), COLORS.get('status', curses.A_DIM))
        except curses.error:
            pass

    def _draw_page(stdscr, H, W, partial):
        """Draw category detail page."""
        nonlocal last_spinner_frame
        PAD = 2
        status_y = H - 1

        # ── Row 0: Back + page title + count ──
        all_items, selected_items, filtered_items = get_current_data()
        page_title = f"← {panes[current_pane]}"
        count_str = f"{len(selected_items)}/{len(all_items)}"
        title_attr = COLORS.get('accent', curses.A_BOLD)
        try:
            stdscr.addstr(0, PAD, page_title, title_attr)
            stdscr.addstr(0, W - len(count_str) - PAD, count_str, curses.A_DIM)
        except curses.error:
            pass

        # ── Row 1: Divider ──
        if not partial:
            draw_line(stdscr, 1, PAD, W - PAD * 2)

        # ── Row 2+: Filter indicator ──
        list_start_y = 2
        if filter_text and not partial:
            try:
                stdscr.addstr(list_start_y, PAD, f"/ {filter_text}", COLORS.get('info', curses.A_DIM))
            except curses.error:
                pass
            list_start_y += 1

        # ── List area ──
        log_lines_count = min(4, max(1, len(log.lines)))
        log_area = log_lines_count + 2
        list_end_y = status_y - log_area
        list_h = list_end_y - list_start_y

        if not partial and list_h > 0:
            if not filtered_items:
                msg = "nothing here" if not all_items else f"no matches for '{filter_text}'"
                try:
                    stdscr.addstr(list_start_y + 1, PAD + 2, msg, curses.A_DIM)
                except curses.error:
                    pass
            else:
                view_h = list_h
                start_idx = max(0, idx - view_h + 1) if idx >= view_h else 0
                for i, item in enumerate(filtered_items[start_idx:start_idx + view_h]):
                    real_idx = start_idx + i
                    is_sel = item in selected_items
                    is_cur = real_idx == idx

                    cursor = "▸ " if is_cur else "  "
                    check = "✓ " if is_sel else "· "
                    text = f"{cursor}{check}{item}"

                    if is_cur:
                        attr = COLORS.get('cursor', curses.A_REVERSE)
                    elif is_sel:
                        attr = COLORS.get('success', curses.A_BOLD)
                    else:
                        attr = curses.A_DIM
                    try:
                        stdscr.addstr(list_start_y + i, PAD, text[:W - PAD * 2].ljust(W - PAD * 2), attr)
                    except curses.error:
                        pass

        # ── Log area ──
        log_divider_y = list_end_y
        usable_w = W - PAD * 2

        if log.lines:
            draw_line(stdscr, log_divider_y, PAD, usable_w)
            log_view_h = min(log_lines_count, status_y - log_divider_y - 1)
            view_start = max(0, len(log.lines) - log_view_h - log.scroll)
            view_end = view_start + log_view_h
            for i, line in enumerate(log.lines[view_start:view_end]):
                color = curses.A_DIM
                if line.startswith(ICONS["success"]):
                    color = COLORS.get('success', curses.A_DIM)
                elif line.startswith(ICONS["error"]):
                    color = COLORS.get('error', curses.A_DIM)
                elif line.startswith(ICONS["warn"]):
                    color = COLORS.get('warn', curses.A_DIM)
                padded = line[:usable_w].ljust(usable_w)
                try:
                    stdscr.addstr(log_divider_y + 1 + i, PAD, padded, color)
                except curses.error:
                    pass
            painted = len(log.lines[view_start:view_end])
            for extra in range(log_view_h - painted):
                try:
                    stdscr.addstr(log_divider_y + 1 + painted + extra, PAD, ' ' * usable_w)
                except curses.error:
                    pass

        # ── Status bar ──
        if is_running:
            frame = int(time.time() * 4) % 4
            last_spinner_frame = frame
            dots = "·" * (frame + 1)
            label = running_label or "working"
            status = f"  {dots} {label}"
        else:
            status = f"  {HINT_PAGE}"
        try:
            stdscr.addstr(status_y, 0, status[:W].ljust(W), COLORS.get('status', curses.A_DIM))
        except curses.error:
            pass

    def run_async(name, func, on_success=None):
        """Run function asynchronously; worker is headless (no curses)."""
        nonlocal action_thread, is_running, running_label
        if action_thread and action_thread.is_alive():
            logger("warn", "Operation already running")
            return
        log.clear()
        logger("info", f"Starting {name}...")
        is_running = True
        running_label = name
        draw()

        def wrapper():
            nonlocal is_running, running_label
            try:
                result = func()
                if callable(on_success):
                    on_success(result)
                else:
                    ui_events.put(("toast", False, f"{ICONS['success']} {name} Complete", ["Operation completed successfully"]))
            except Exception as e:
                logger("error", f"{name} failed: {e}")
                ui_events.put(("toast", True, f"{ICONS['error']} {name} Failed", [str(e), "Check the log panel"]))
            finally:
                is_running = False
                running_label = None

        action_thread = threading.Thread(target=wrapper, daemon=True)
        action_thread.start()

    def stow_selected():
        """Stow selected packages"""
        if not selected_stow:
            logger("warn", "No stow packages selected")
            return

        if not check_stow():
            logger("error", "GNU Stow is not installed. Install with: sudo pacman -Sy --noconfirm stow")
            return

        if not STOW_DIR.exists():
            logger("error", f"Stow directory does not exist: {STOW_DIR}")
            return

        # Build command
        selected_list = sorted(selected_stow)
        cmd_parts = ["stow", "-v", "-R", "-t", "$HOME"] + [shlex.quote(pkg) for pkg in selected_list]
        cmd = " ".join(cmd_parts)

        logger("info", f"Stowing {len(selected_list)} packages...")

        exit_code = run(cmd, logger, cwd=str(STOW_DIR))

        if exit_code != 0:
            raise Exception(f"Stow failed with exit code {exit_code}")

        return selected_list

    def install_packages_no_prompt():
        """Install selected system packages (sudo already cached). Worker-safe."""
        if not selected_pkgs:
            logger("warn", "No system packages selected")
            return []
        selected_list = list(selected_pkgs)
        logger("info", f"Installing {len(selected_list)} packages...")
        def ops_logger(msg):
            logger("info", str(msg))
        ensure_packages(selected_list, logger=ops_logger)
        logger("success", "System packages installed")
        return selected_list

    def clone_plugins():
        """Clone selected plugin repositories"""
        if not selected_plugins:
            logger("warn", "No plugins selected")
            return

        # Filter config to only selected plugins
        cfg_filtered = dict(cfg)
        filtered_repos = []

        for repo in cfg.get('repos', []):
            dest = repo.get('dest', '')
            if '/.oh-my-zsh/custom/plugins/' in dest:
                plugin_name = dest.split('/.oh-my-zsh/custom/plugins/')[-1]
                if plugin_name in selected_plugins:
                    filtered_repos.append(repo)
            else:
                filtered_repos.append(repo)

        cfg_filtered['repos'] = filtered_repos
        logger("info", f"Cloning {len(filtered_repos)} repositories...")

        # Create wrapper logger for ops module (expects single argument)
        def ops_logger(msg):
            logger("info", str(msg))

        result = clone_repos(cfg_filtered, logger=ops_logger)
        return [f"{repo.get('url', 'unknown')} -> {repo.get('dest', 'unknown')}"
                for repo in filtered_repos]    # Initial setup - check for available data
    if not stow_pkgs and not sys_pkgs and not plugins:
        logger("warn", "No packages or plugins found")
        if not STOW_DIR.exists():
            logger("info", f"Create stow directory: mkdir -p {STOW_DIR}")
    elif not stow_pkgs:
        logger("info", f"No stow packages found in {STOW_DIR}")

    apply_filter()  # Initialize filtered lists
    draw()  # Initial screen draw

    # Main event loop
    while True:
        try:
            # Drain UI events first (toasts, etc.)
            try:
                while True:
                    kind, is_error, title, lines = ui_events.get_nowait()
                    if kind == "toast":
                        toast(stdscr, title, lines, is_error=is_error)
                        stdscr.getch()
                        log.clear()
                        log.dirty = True
                        suppress_enter_once = True
            except queue.Empty:
                pass

            c = stdscr.getch()
        except KeyboardInterrupt:
            break

        # Help overlay: any key dismisses
        if show_help:
            if c != -1:
                show_help = False
                draw()
            if show_help:
                continue

        # ────── Menu view ──────
        if view == "menu":
            if c in (ord('q'),):
                break
            elif c in (curses.KEY_UP, ord('k')):
                menu_idx = max(0, menu_idx - 1)
            elif c in (curses.KEY_DOWN, ord('j')):
                menu_idx = min(len(panes) - 1, menu_idx + 1)
            elif c in (10, 13):  # Enter → open page
                current_pane = menu_idx
                idx = 0
                filter_text = ""
                apply_filter()
                view = "page"
            elif c == ord('?'):
                show_help = True

        # ────── Page view ──────
        elif view == "page":
            # Back to menu
            if c == ord('b'):
                view = "menu"
                filter_text = ""

            # Navigation
            elif c in (curses.KEY_UP, ord('k')):
                idx = max(0, idx - 1)
            elif c in (curses.KEY_DOWN, ord('j')):
                _, _, current_filtered = get_current_data()
                idx = min(max(0, len(current_filtered) - 1), idx + 1)
            elif c == curses.KEY_HOME:
                idx = 0
            elif c == curses.KEY_END:
                _, _, current_filtered = get_current_data()
                idx = max(0, len(current_filtered) - 1)
            elif c == curses.KEY_PPAGE:
                _, _, current_filtered = get_current_data()
                if len(current_filtered) > 10:
                    idx = max(0, idx - 10)
                else:
                    log.scroll = min(len(log.lines), log.scroll + 10)
                    log.follow = False
            elif c == curses.KEY_NPAGE:
                _, _, current_filtered = get_current_data()
                if len(current_filtered) > 10:
                    idx = min(max(0, len(current_filtered) - 1), idx + 10)
                else:
                    log.scroll = max(0, log.scroll - 10)
                    if log.scroll == 0:
                        log.follow = True

            # Selection
            elif c == ord(' '):
                _, current_selected, current_filtered = get_current_data()
                if current_filtered and idx < len(current_filtered):
                    item = current_filtered[idx]
                    if item in current_selected:
                        current_selected.remove(item)
                    else:
                        current_selected.add(item)
            elif c in (ord('A'), ord('a')):
                _, current_selected, current_filtered = get_current_data()
                current_selected.update(current_filtered)
            elif c in (ord('U'), ord('u')):
                _, current_selected, current_filtered = get_current_data()
                for item in current_filtered:
                    current_selected.discard(item)
            elif c in (ord('I'), ord('i')):
                _, current_selected, current_filtered = get_current_data()
                for item in current_filtered:
                    if item in current_selected:
                        current_selected.remove(item)
                    else:
                        current_selected.add(item)

            # Run action
            elif c in (10, 13):
                if suppress_enter_once:
                    suppress_enter_once = False
                elif not is_running:
                    if current_pane == 0:
                        run_async("Stow packages", stow_selected)
                    elif current_pane == 1:
                        if not selected_themes:
                            ui_events.put(("toast", False, f"{ICONS['warn']} No themes selected", ["Select one or more themes"]))
                        else:
                            def do_copy():
                                names = sorted(selected_themes)
                                return copy_themes_worker(names, logger)

                            def after_copy(summary):
                                dry = summary.get("dry")
                                ok = summary.get("ok", 0)
                                errors = summary.get("errors", 0)
                                skipped = summary.get("skipped", 0)
                                title = f"{ICONS['success']} Copied {ok} theme(s)" if errors == 0 else f"{ICONS['warn']} Copy completed with issues"
                                suffix = " — dry run" if dry else ""
                                ui_events.put(("toast", errors > 0, title, [f"ok {ok}, skipped {skipped}, errors {errors}{suffix}"]))

                            run_async("Copying themes…", do_copy, on_success=after_copy)
                    elif current_pane == 2:
                        if ensure_sudo_cached_on_main(stdscr, logger):
                            run_async("Install packages", install_packages_no_prompt)
                    elif current_pane == 3:
                        run_async("Clone plugins", clone_plugins)

            elif c == ord('r'):
                cfg = load_config()
                stow_pkgs = list_packages()
                themes_map = discover_themes()
                theme_names = sorted(themes_map.keys())
                sys_pkgs = package_plan(cfg)
                plugin_repos = [r for r in cfg.get("repos", []) if "/.oh-my-zsh/custom/plugins/" in r.get("dest", "")]
                plugins = [r["dest"].split("/.oh-my-zsh/custom/plugins/")[-1] for r in plugin_repos]
                selected_stow &= set(stow_pkgs)
                selected_themes &= set(theme_names)
                selected_pkgs &= set(sys_pkgs)
                selected_plugins &= set(plugins)
                apply_filter()
                logger("info", "Refreshed")
            elif c == ord('c'):
                log.clear()

            # Filter
            elif c == ord('/'):
                curses.curs_set(1)
                try:
                    H, W = stdscr.getmaxyx()
                    prompt = "/ "
                    stdscr.addstr(H - 1, 0, prompt.ljust(W), curses.A_DIM)
                    stdscr.refresh()
                    filter_input = filter_text
                    while True:
                        fc = stdscr.getch()
                        if fc in (10, 13):
                            break
                        elif fc == 27:
                            filter_input = ""
                            break
                        elif fc in (curses.KEY_BACKSPACE, 127, 8):
                            if filter_input:
                                filter_input = filter_input[:-1]
                        elif 32 <= fc <= 126:
                            filter_input += chr(fc)
                        display = f"{prompt}{filter_input}".ljust(W)
                        stdscr.addstr(H - 1, 0, display, curses.A_DIM)
                        stdscr.refresh()
                    filter_text = filter_input
                    apply_filter()
                finally:
                    curses.curs_set(0)

            elif c == ord('?'):
                show_help = True
            elif c in (ord('F'), ord('f')):
                log.follow = not log.follow
                if log.follow:
                    log.scroll = 0
            elif c in (ord('G'), ord('g')):
                log.follow = True
                log.scroll = 0

            # Selective cleanup (D) — stow page only
            elif c == ord('D') and current_pane == 0 and not is_running:
                if not selected_stow:
                    ui_events.put(("toast", False, f"{ICONS['warn']} No stow packages selected", ["Select packages first"]))
                else:
                    selected_list = sorted(selected_stow)
                    if not STOW_DIR.exists():
                        ui_events.put(("toast", True, f"{ICONS['error']} Missing stow directory", [str(STOW_DIR)]))
                    else:
                        files, dirs = enumerate_stow_targets_for_pkgs(selected_list)
                        targets_preview = files + dirs
                        if not targets_preview:
                            ui_events.put(("toast", False, f"{ICONS['warn']} Nothing to remove", ["No targets from selected packages"]))
                        else:
                            if confirm_remove_dialog(stdscr, targets_preview):
                                def do_cleanup():
                                    return selective_cleanup_worker(files, dirs, logger)

                                def after_cleanup(summary):
                                    dry = summary.get('dry_run')
                                    fr = summary.get('files_removed', 0)
                                    dr = summary.get('dirs_removed', 0)
                                    sk = summary.get('skipped', 0)
                                    er = summary.get('errors', 0)
                                    t = f"{ICONS['success']} Cleanup complete" if er == 0 else f"{ICONS['warn']} Cleanup had issues"
                                    sfx = " [DRY]" if dry else ""
                                    ui_events.put(("toast", er > 0, t, [f"files {fr}, dirs {dr}, skipped {sk}, errors {er}{sfx}"]))

                                run_async("Cleaning…", do_cleanup, on_success=after_cleanup)
                            else:
                                logger("info", "Cleanup cancelled")

        # Decide if redraw needed
        need_draw = False
        spinner_frame_changed = False
        if is_running:
            frame = int(time.time() * 4) % 4
            if frame != last_spinner_frame:
                spinner_frame_changed = True
                last_spinner_frame = frame
        user_input = c != -1
        log_update = log.dirty
        if user_input or log_update or spinner_frame_changed:
            need_draw = True
        if need_draw:
            now = time.time()
            only_log = (not user_input) and log_update and not show_help and not spinner_frame_changed
            only_spinner = spinner_frame_changed and not user_input and not log_update and not show_help
            if only_log and now - last_log_redraw_time < LOG_REDRAW_INTERVAL:
                pass
            else:
                if only_log:
                    draw(partial=True)
                    last_log_redraw_time = now
                elif only_spinner:
                    draw(partial=True)
                else:
                    draw()

if __name__ == "__main__":  # safety fallback if run directly
    curses.wrapper(main)

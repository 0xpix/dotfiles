import os, subprocess, shlex, pathlib, errno
from typing import Callable, List, Tuple, Dict, Any
try:
    import yaml  # type: ignore
except Exception:  # ModuleNotFoundError or any import issue
    yaml = None  # will be installed lazily

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = ROOT / "config.yaml"
STOW_DIR = ROOT / "stow"
Logger = Callable[[str], None]

def run(cmd, sudo=False, check=True, env=None, logger: Logger | None = None):
    """Run a command streaming output line-by-line to logger (or print)."""
    if sudo and os.geteuid() != 0:
        # Use stored password if available
        sudo_password = os.environ.get('SUDO_PASSWORD')
        if sudo_password:
            cmd = f"echo '{sudo_password}' | sudo -S -E {cmd}"
        else:
            cmd = f"sudo -E {cmd}"
    if logger is None:
        logger = print  # type: ignore
    logger(f"[cmd] {cmd}")
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, text=True, bufsize=1)
    collected: List[str] = []
    for raw in proc.stdout or []:  # type: ignore
        line = raw.rstrip('\n')
        collected.append(line)
        logger(line)
    proc.wait()
    rc = proc.returncode
    logger(f"[exit {rc}] {cmd}")
    if check and rc != 0:
        tail = '\n'.join(collected[-40:])  # include last 40 lines for context
        raise RuntimeError(f"Command failed (exit {rc}): {cmd}\n--- output tail ---\n{tail}")
    return rc

def which(bin_name):
    return subprocess.call(f"command -v {shlex.quote(bin_name)} >/dev/null 2>&1", shell=True) == 0

def load_config():
    """Load YAML config, installing PyYAML on demand if missing.

    This keeps the module importable on systems without PyYAML yet, allowing
    ensure_python_yaml() to run first. Idempotent: once installed, subsequent
    calls reuse the imported module.
    """
    global yaml
    if yaml is None:
        # Attempt installation then import again
        try:
            ensure_python_yaml()
        except NameError:
            # ensure_python_yaml defined later; call after it exists via recursion
            pass
        try:
            import yaml as _yaml  # type: ignore
            yaml = _yaml
        except Exception as e:
            raise RuntimeError("Unable to import PyYAML after installation attempt: " + str(e))
    with open(CONFIG, "r") as f:
        return yaml.safe_load(f) or {}

def detect_distro():
    """Kept for backward compatibility but unused. Arch is assumed."""
    return "arch"

def ensure_packages(pkgs, logger: Logger | None = None):
    """Install packages on Arch Linux.

    - Sync pacman database.
    - Install official repo packages via pacman.
    - If AUR packages are present and yay/paru exists, install them via that helper.
      Otherwise log a warning.
    """
    if not pkgs:
        return []

    log = logger or print  # type: ignore

    # Always refresh pacman databases first
    run("pacman -Sy --noconfirm", sudo=True, logger=logger)

    # Partition into official vs potential AUR by probing pacman -Si
    official: list[str] = []
    aur: list[str] = []
    for p in pkgs:
        try:
            rc = subprocess.call(f"pacman -Si {shlex.quote(p)} >/dev/null 2>&1", shell=True)
            if rc == 0:
                official.append(p)
            else:
                aur.append(p)
        except Exception:
            aur.append(p)

    if official:
        run(f"pacman -S --needed --noconfirm {' '.join(shlex.quote(p) for p in official)}", sudo=True, logger=logger)

    if aur:
        helper = None
        if which("yay"):
            helper = "yay"
        elif which("paru"):
            helper = "paru"
        if helper:
            # AUR helpers handle privilege escalation internally; do not pass sudo
            run(f"{helper} -S --needed --noconfirm {' '.join(shlex.quote(p) for p in aur)}", sudo=False, logger=logger)
        else:
            log(f"[warn] AUR helper not found (yay/paru). Unable to install: {' '.join(aur)}")

    return pkgs

def package_plan(cfg):
    """Return list of packages to install.

    Supports two formats in config.yaml:
    - New (Arch-only):
        packages:
          - pkg1
          - pkg2
    - Legacy (multi-distro):
        packages:
          common: [foo]
          arch: [bar]
    """
    section = cfg.get("packages", [])
    if isinstance(section, list):
        return list(section)
    if isinstance(section, dict):
        common = section.get("common", []) or []
        arch_specific = section.get("arch", []) or []
        seen, out = set(), []
        for p in (list(common) + list(arch_specific)):
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out
    return []

def ensure_stow(logger: Logger | None = None):
    if not which("stow"):
        try:
            run("pacman -Sy --noconfirm stow", sudo=True, logger=logger)
        except RuntimeError:
            raise RuntimeError("Install stow manually first")

def do_stow(cfg, target_home=True, dry=False, logger: Logger | None = None):
    """Safely stow selected packages.

    Changes vs previous implementation:
    - Aggregate stow invocation when possible to let stow handle overlaps.
    - Only back up individual conflicting files/symlinks, never whole .config dirs.
    - Skip backing up directories entirely; rely on stow's --no-folding style by keeping
      package directory layouts minimal (.config/app/...). If a directory exists, we do not
      delete or move it—only conflicting files at the leaf level are backed up.
    - Avoid repeatedly restowing each package which previously could cause broad symlinks.
    """
    use_native_stow = os.environ.get("DOTFILES_USE_STOW") == "1"
    packages = [p for p in cfg.get("stow", []) if (STOW_DIR / p).is_dir()]
    missing = [p for p in cfg.get("stow", []) if p not in packages]
    for m in missing:
        (logger or print)(f"[warn] missing stow package: {m}")
    if not packages:
        return []

    # Native stow path (previous logic) guarded by env flag
    if use_native_stow:
        ensure_stow(logger=logger)
        home = pathlib.Path(os.path.expanduser("~")) if target_home else STOW_DIR.parent

        def iter_package_entries():
            for pkg in packages:
                root = STOW_DIR / pkg
                for path in root.rglob('*'):
                    if path.is_dir():
                        continue
                    rel = path.relative_to(root)
                    yield pkg, path, rel

        backup_root = pathlib.Path(os.path.expanduser("~/.dotfiles_backup"))
        backup_root.mkdir(parents=True, exist_ok=True)

        def backup_file(target_path: pathlib.Path):
            from datetime import datetime
            rel_name = target_path.name
            dest = backup_root / f"{rel_name}.orig"
            if dest.exists():
                ts = datetime.now().strftime("%Y%m%d%H%M%S")
                dest = backup_root / f"{rel_name}.orig.{ts}"
            try:
                target_path.rename(dest)
                (logger or print)(f"[backup] {target_path} -> {dest}")
            except Exception as e:
                (logger or print)(f"[warn] backup failed {target_path}: {e}")

        seen_conflicts = 0
        for _pkg, _path, rel in iter_package_entries():
            target_path = home / rel
            if not target_path.exists():
                continue
            if target_path.is_symlink():
                try:
                    real = target_path.resolve()
                    if str(real).startswith(str(STOW_DIR)):
                        continue
                except Exception:
                    pass
                backup_file(target_path); seen_conflicts += 1; continue
            if target_path.is_file():
                backup_file(target_path); seen_conflicts += 1
        if seen_conflicts:
            (logger or print)(f"[info] backed up {seen_conflicts} conflicting files")
        pkgs_str = ' '.join(shlex.quote(p) for p in packages)
        simulate = os.environ.get("DOTFILES_STOW_DRY_RUN") == "1"
        base_cmd = "stow -v -R" + (" -n" if simulate else "")
        cmd = f"{base_cmd} -t $HOME {pkgs_str}" if target_home else f"{base_cmd} {pkgs_str}"
        if dry:
            (logger or print)(f"[dry] {cmd} (cwd={STOW_DIR})")
        else:
            for p in packages:
                (logger or print)(f"[stow] package root: {(STOW_DIR/p)}")
            (logger or print)(f"[stow] running aggregated: {cmd}{' (simulate)' if simulate else ''}")
            env = {**os.environ, "HOME": os.path.expanduser("~"), "PWD": str(STOW_DIR)}
            run(f"cd {shlex.quote(str(STOW_DIR))} && {cmd}", sudo=False, check=True, env=env, logger=logger)
        return packages

    # Safe manual symlink mode (default)
    home = pathlib.Path(os.path.expanduser("~"))
    backup_root = pathlib.Path(os.path.expanduser("~/.dotfiles_backup"))
    backup_root.mkdir(parents=True, exist_ok=True)

    # Warn about multi-app bundling inside a single package's .config directory.
    for pkg in packages:
        pkg_dir = STOW_DIR / pkg
        cfg_dir = pkg_dir / '.config'
        if cfg_dir.is_dir():
            # collect first-level entries in .config
            children = [p.name for p in cfg_dir.iterdir() if p.is_dir() or p.is_file()]
            # if more than one top-level application directory/file, warn user
            # (ghostty package currently seems to include unrelated apps)
            unique = [c for c in children if not c.startswith('.')]
            if len(unique) > 1:
                (logger or print)(f"[warn] package '{pkg}' bundles multiple apps in .config: {', '.join(unique)}. Consider splitting into separate stow packages.")

    # Guard: if ~/.config itself is a symlink pointing inside the stow tree, abort to prevent
    # further implicit 'adoption' of unrelated configs into a single package.
    home_config = home / '.config'
    try:
        if home_config.is_symlink():
            resolved = home_config.resolve()
            if str(resolved).startswith(str(STOW_DIR)):
                (logger or print)(
                    f"[error] Aborting: ~/.config is a symlink to {resolved} inside your stow repo.\n"
                    "        This causes every new config added under ~/.config to appear in that single package.\n"
                    "        Fix: Remove the symlink, recreate a real ~/.config, and split multi-app packages."
                )
                return []
    except Exception as e:
        (logger or print)(f"[warn] could not inspect ~/.config symlink: {e}")

    def backup(target: pathlib.Path):
        from datetime import datetime
        rel_name = target.name
        dest = backup_root / f"{rel_name}.orig"
        if dest.exists():
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            dest = backup_root / f"{rel_name}.orig.{ts}"
        try:
            target.rename(dest)
            (logger or print)(f"[backup] {target} -> {dest}")
        except Exception as e:
            (logger or print)(f"[warn] backup failed {target}: {e}")

    created, skipped, conflicts = 0,0,0
    adopt_dirs = os.environ.get("DOTFILES_ADOPT") == "1"
    dir_links: set[pathlib.Path] = set()
    for pkg in packages:
        pkg_dir = STOW_DIR / pkg
        (logger or print)(f"[link] processing package {pkg}")
        # First pass: create symlinks for immediate .config/<name> directories
        cfg_root = pkg_dir / '.config'
        if cfg_root.is_dir():
            for child in cfg_root.iterdir():
                if not child.is_dir():
                    continue
                rel_dir = child.relative_to(pkg_dir)  # .config/<name>
                target_dir = home / rel_dir
                # If target already correct symlink, skip
                if target_dir.is_symlink():
                    try:
                        if target_dir.resolve() == child.resolve():
                            skipped += 1
                            dir_links.add(child)
                            continue
                    except Exception:
                        pass
                if target_dir.exists() and not target_dir.is_symlink():
                    if adopt_dirs:
                        # Back up existing directory then replace with symlink
                        from datetime import datetime
                        ts = datetime.now().strftime("%Y%m%d%H%M%S")
                        backup_path = backup_root / f"{rel_dir.name}.dir.orig.{ts}"
                        try:
                            target_dir.rename(backup_path)
                            (logger or print)(f"[adopt-backup] {target_dir} -> {backup_path}")
                        except Exception as e:
                            (logger or print)(f"[warn] adopt backup failed for {target_dir}: {e}")
                            skipped += 1
                            continue
                    else:
                        (logger or print)(f"[skip-dir-existing] {target_dir} exists; not replacing with symlink to {child} (set DOTFILES_ADOPT=1 to adopt)")
                        skipped += 1
                        continue
                if dry:
                    (logger or print)(f"[dry-dir] {target_dir} -> {child}")
                    continue
                try:
                    # Ensure parent of target_dir exists
                    target_dir.parent.mkdir(parents=True, exist_ok=True)
                    target_dir.symlink_to(child)
                    dir_links.add(child)
                    created += 1
                    (logger or print)(f"[symlink-dir] {target_dir} -> {child}")
                except Exception as e:
                    (logger or print)(f"[error] symlink-dir {target_dir}: {e}")

        for path in pkg_dir.rglob('*'):
            # Skip any .git directories and their contents
            if '.git' in path.parts:
                continue
            if path.is_dir():
                continue  # only link files in second pass
            # Skip files inside directories we already symlinked as a whole
            try:
                for d in dir_links:
                    try:
                        # Python 3.9+ has is_relative_to; fallback to startswith if missing
                        rel = False
                        if hasattr(path, 'is_relative_to'):
                            rel = path.is_relative_to(d)  # type: ignore[attr-defined]
                        else:  # pragma: no cover
                            rel = str(path).startswith(str(d)+os.sep)
                        if rel:
                            # (logger or print)(f"[skip-contained] {path} inside {d}")  # verbose debug (disabled)
                            raise StopIteration  # break both loops
                    except StopIteration:
                        raise
                # normal flow continues if not inside dir_links
            except StopIteration:
                continue
            except Exception:
                pass
            rel = path.relative_to(pkg_dir)
            # Never attempt to create a symlink that replaces the root ~/.config directory itself
            if str(rel) == '.config':  # defensive guard; shouldn't normally happen for files
                (logger or print)(f"[skip] refusing to link top-level .config from {pkg}")
                skipped += 1
                continue
            target = home / rel
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                (logger or print)(f"[warn] could not ensure parent dir for {target}: {e}")
                continue
            if target.exists() or target.is_symlink():
                # Already correct symlink?
                if target.is_symlink():
                    try:
                        if target.resolve() == path.resolve():
                            skipped += 1
                            continue
                    except Exception:
                        pass
                if target.is_dir():
                    # We do not overwrite real directories; user must relocate contents manually if desired
                    (logger or print)(f"[skip-dir] {target} exists as directory; leaving intact")
                    skipped += 1
                    continue
                backup(target)
                conflicts += 1
            if dry:
                (logger or print)(f"[dry-link] {target} -> {path}")
                continue
            try:
                target.symlink_to(path)
                created += 1
                (logger or print)(f"[symlink] {target} -> {path}")
            except OSError as e:
                if e.errno == errno.EEXIST:
                    (logger or print)(f"[exists] {target} already exists; skipped (EEXIST)")
                    skipped += 1
                else:
                    (logger or print)(f"[error] symlink {target}: {e}")
            except Exception as e:
                (logger or print)(f"[error] symlink {target}: {e}")
    (logger or print)(f"[summary] created={created} skipped={skipped} conflicts_backed_up={conflicts}")
    return packages

def ensure_zsh_default(logger: Logger | None = None):
    zsh = subprocess.check_output("command -v zsh || true", shell=True).decode().strip()
    if not zsh:
        (logger or print)("[info] zsh not installed yet; skipping chsh")
        return
    current = os.environ.get("SHELL","")
    if "zsh" in current:
        (logger or print)("[ok] default shell already zsh")
        return
    run(f"chsh -s {zsh} $USER || true", sudo=False, check=False, logger=logger)
    (logger or print)("[note] You may need to log out/in for default shell to apply.")

def clone_repos(cfg, logger: Logger | None = None):
    results: List[Tuple[str,str]] = []
    for repo in cfg.get("repos",[]):
        dest = os.path.expanduser(repo["dest"])
        url = repo["url"]
        pathlib.Path(dest).parent.mkdir(parents=True, exist_ok=True)
        if pathlib.Path(dest).exists():
            (logger or print)(f"[skip] {dest}")
            results.append((dest, "skipped"))
            continue
        run(f"git clone --depth 1 {shlex.quote(url)} {shlex.quote(dest)}", logger=logger)
        results.append((dest, "cloned"))
    return results

def run_post(cfg, logger: Logger | None = None):
    executed: List[str] = []
    for cmd in cfg.get("post", []):
        run(cmd, sudo=False, check=False, logger=logger)
        executed.append(cmd)
    return executed

def ensure_python_yaml(logger: Logger | None = None):
    global yaml
    if yaml is not None:
        return
    # Arch: best-effort system package first
    run("pacman -S --needed --noconfirm python-yaml python-pip || true", sudo=True, check=False, logger=logger)
    # fallback to pip
    # ensure pip exists (some minimal installs lack it)
    run("python3 -m ensurepip --upgrade || true", sudo=False, check=False, logger=logger)
    run("python3 -m pip install --user --upgrade pip pyyaml || true", sudo=False, check=False, logger=logger)
    try:
        import yaml as _yaml  # type: ignore
        yaml = _yaml
    except Exception:
        pass

def full_setup(dry=False, logger: Logger | None = None):
    ensure_python_yaml(logger=logger)
    cfg = load_config()
    summary: Dict[str, Any] = {}
    pkgs = package_plan(cfg)
    if pkgs and not dry:
        summary['packages'] = ensure_packages(pkgs, logger=logger)
    else:
        summary['packages'] = []
    summary['stow'] = do_stow(cfg, dry=dry, logger=logger)
    ensure_zsh_default(logger=logger)
    summary['repos'] = clone_repos(cfg, logger=logger)
    summary['post'] = run_post(cfg, logger=logger)
    (logger or print)("[done] full setup complete")
    return summary

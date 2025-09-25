from .ops import package_plan, ensure_packages, load_config

def install_selected(selected):
    cfg = load_config()
    pkgs = package_plan(cfg)
    final = [p for p in pkgs if (not selected or p in selected)]
    ensure_packages(final)

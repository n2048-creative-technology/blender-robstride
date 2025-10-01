import os
import sys
import subprocess
from typing import Tuple


def _addon_root() -> str:
    return os.path.dirname(__file__)


def _vendor_dir() -> str:
    return os.path.join(_addon_root(), "vendor")


def _wheels_dir() -> str:
    return os.path.join(_addon_root(), "wheels")


def add_vendor_to_path() -> None:
    v = _vendor_dir()
    if os.path.isdir(v) and v not in sys.path:
        sys.path.insert(0, v)


def have_modules() -> Tuple[bool, bool, bool]:
    try:
        import can  # noqa: F401
        has_can = True
    except Exception:
        has_can = False
    try:
        import canopen  # noqa: F401
        has_canopen = True
    except Exception:
        has_canopen = False
    try:
        import robstride  # type: ignore  # noqa: F401
        has_robstride = True
    except Exception:
        has_robstride = False
    return has_can, has_canopen, has_robstride


def install_from_wheels() -> bool:
    wheels = _wheels_dir()
    if not os.path.isdir(wheels):
        return False
    vendor = _vendor_dir()
    os.makedirs(vendor, exist_ok=True)
    # Ensure pip is available
    try:
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])  # noqa: S603
    except Exception:
        pass

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        wheels,
        "-t",
        vendor,
        "python-can",
        "canopen",
        "robstride",
    ]
    try:
        subprocess.check_call(cmd)  # noqa: S603
        return True
    except Exception:
        return False


def ensure_dependencies() -> Tuple[bool, str]:
    add_vendor_to_path()
    has_can, has_canopen, has_robstride = have_modules()
    if has_can and has_canopen:
        return True, "ready"
    # Try installing if wheels are bundled
    if install_from_wheels():
        add_vendor_to_path()
        has_can, has_canopen, has_robstride = have_modules()
        if has_can and has_canopen:
            return True, "installed"
    status = []
    status.append("python-can" if has_can else "missing python-can")
    status.append("canopen" if has_canopen else "missing canopen")
    status.append("robstride" if has_robstride else "missing robstride")
    return False, ", ".join(status)

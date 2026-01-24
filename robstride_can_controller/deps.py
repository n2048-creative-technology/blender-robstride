import os
import sys
from typing import Tuple


def _addon_root() -> str:
    return os.path.dirname(__file__)


def _vendor_dir() -> str:
    return os.path.join(_addon_root(), "vendor")


def _wheels_dir() -> str:
    # Wheels are not used in Extensions per guidelines
    return os.path.join(_addon_root(), "wheels")


def add_vendor_to_path() -> None:
    v = _vendor_dir()
    if os.path.isdir(v) and v not in sys.path:
        sys.path.insert(0, v)


def have_modules() -> Tuple[bool, bool, bool]:
    # Ensure vendored path is available before import checks
    add_vendor_to_path()
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
    # Runtime installation is not performed in Extensions.
    # Dependencies are vendored under the package's vendor directory.
    return False


def ensure_dependencies() -> Tuple[bool, str]:
    add_vendor_to_path()
    has_can, has_canopen, has_robstride = have_modules()
    if has_can and has_canopen:
        return True, "ready"
    # In Extensions, we do not install at runtime. Report status only.
    status = []
    status.append("python-can" if has_can else "missing python-can")
    status.append("canopen" if has_canopen else "missing canopen")
    status.append("robstride" if has_robstride else "missing robstride")
    return False, ", ".join(status)

"""Load user TX/RX functions or classes."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any


def load_target(target: str) -> Any:
    """Load ``module:object`` or ``path/to/file.py:object``."""

    if ":" not in target:
        raise ValueError("target must use 'module:object' or 'file.py:object' syntax")

    module_ref, object_ref = target.split(":", 1)
    if module_ref.endswith(".py") or Path(module_ref).exists():
        module_path = Path(module_ref).resolve()
        module_name = module_path.stem
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot import module from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(module_ref)

    obj: Any = module
    for part in object_ref.split("."):
        obj = getattr(obj, part)
    if inspect.isclass(obj):
        obj = obj()
    return obj

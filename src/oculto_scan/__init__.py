"""Offline scanner for data leaks in construction workbooks (.xlsx/.xlsm)."""

__version__ = "0.1.5"

from oculto_scan.public import diff_bytes, scan_bytes

__all__ = ["__version__", "diff_bytes", "scan_bytes"]

"""
Speech-to-Text Desktop Dictation Service package.
"""

import os
import sys

# Ensure Windows finds the NVIDIA CUDA cuBLAS and cuDNN libraries for CTranslate2
_site_packages = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "Lib", "site-packages", "nvidia")
if os.path.exists(_site_packages):
    for root, dirs, _ in os.walk(_site_packages):
        if "bin" in dirs:
            bin_path = os.path.abspath(os.path.join(root, "bin"))
            os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(bin_path)
                except Exception:
                    pass

__version__ = "1.0.0"


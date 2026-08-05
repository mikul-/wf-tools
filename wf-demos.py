#!/usr/bin/env python3
"""Backward-compat wrapper — delegates to wf-tools.py."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# wf-tools.py has a hyphen in the filename, use importlib
import importlib.util
spec = importlib.util.spec_from_file_location(
    "wf_tools", os.path.join(os.path.dirname(os.path.abspath(__file__)), "wf-tools.py")
)
wf_tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf_tools)

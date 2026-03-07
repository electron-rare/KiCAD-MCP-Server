"""
Runtime-oriented unit tests for writable state and library discovery fallbacks.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path


PYTHON_ROOT = Path(__file__).parent.parent / "python"


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, PYTHON_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


platform_helper = load_module("platform_helper", "utils/platform_helper.py")
sys.modules["utils.platform_helper"] = platform_helper
jlcpcb_parts = load_module("jlcpcb_parts", "commands/jlcpcb_parts.py")
library = load_module("library", "commands/library.py")
library_symbol = load_module("library_symbol", "commands/library_symbol.py")

JLCPCBPartsManager = jlcpcb_parts.JLCPCBPartsManager
LibraryManager = library.LibraryManager
SymbolLibraryManager = library_symbol.SymbolLibraryManager


class RuntimePathTests(unittest.TestCase):
    def test_jlcpcb_parts_manager_uses_user_writable_data_dir(self):
        with tempfile.TemporaryDirectory() as td:
            original = os.environ.get("KICAD_MCP_DATA_DIR")
            os.environ["KICAD_MCP_DATA_DIR"] = str(Path(td) / "runtime-data")
            try:
                manager = JLCPCBPartsManager()
                try:
                    self.assertTrue(Path(manager.db_path).exists())
                    self.assertEqual(
                        Path(manager.db_path),
                        Path(td) / "runtime-data" / "jlcpcb_parts.db",
                    )
                finally:
                    manager.conn.close()
            finally:
                if original is None:
                    os.environ.pop("KICAD_MCP_DATA_DIR", None)
                else:
                    os.environ["KICAD_MCP_DATA_DIR"] = original

    def test_footprint_library_manager_discovers_directories_without_fp_lib_table(self):
        with tempfile.TemporaryDirectory() as td:
            footprint_root = Path(td) / "footprints"
            (footprint_root / "Sensor.pretty").mkdir(parents=True)
            (footprint_root / "Power.pretty").mkdir()

            original_env = os.environ.get("KICAD9_FOOTPRINT_DIR")
            original_get_table = LibraryManager._get_global_fp_lib_table
            original_find_3rdparty = LibraryManager._find_kicad_3rdparty_dir

            os.environ["KICAD9_FOOTPRINT_DIR"] = str(footprint_root)
            LibraryManager._get_global_fp_lib_table = lambda self: None
            LibraryManager._find_kicad_3rdparty_dir = lambda self: None
            try:
                manager = LibraryManager()
                self.assertEqual(
                    manager.get_library_path("Sensor"),
                    str(footprint_root / "Sensor.pretty"),
                )
                self.assertEqual(
                    manager.get_library_path("Power"),
                    str(footprint_root / "Power.pretty"),
                )
            finally:
                LibraryManager._get_global_fp_lib_table = original_get_table
                LibraryManager._find_kicad_3rdparty_dir = original_find_3rdparty
                if original_env is None:
                    os.environ.pop("KICAD9_FOOTPRINT_DIR", None)
                else:
                    os.environ["KICAD9_FOOTPRINT_DIR"] = original_env

    def test_symbol_library_manager_discovers_files_without_sym_lib_table(self):
        with tempfile.TemporaryDirectory() as td:
            symbol_root = Path(td) / "symbols"
            symbol_root.mkdir(parents=True)
            (symbol_root / "Device.kicad_sym").write_text(
                "(kicad_symbol_lib)", encoding="utf-8"
            )
            (symbol_root / "MCU.kicad_sym").write_text(
                "(kicad_symbol_lib)", encoding="utf-8"
            )

            original_env = os.environ.get("KICAD9_SYMBOL_DIR")
            original_get_table = SymbolLibraryManager._get_global_sym_lib_table
            original_find_3rd_party = SymbolLibraryManager._find_3rd_party_dir

            os.environ["KICAD9_SYMBOL_DIR"] = str(symbol_root)
            SymbolLibraryManager._get_global_sym_lib_table = lambda self: None
            SymbolLibraryManager._find_3rd_party_dir = lambda self: None
            try:
                manager = SymbolLibraryManager()
                self.assertEqual(
                    manager.libraries["Device"],
                    str(symbol_root / "Device.kicad_sym"),
                )
                self.assertEqual(
                    manager.libraries["MCU"],
                    str(symbol_root / "MCU.kicad_sym"),
                )
            finally:
                SymbolLibraryManager._get_global_sym_lib_table = original_get_table
                SymbolLibraryManager._find_3rd_party_dir = original_find_3rd_party
                if original_env is None:
                    os.environ.pop("KICAD9_SYMBOL_DIR", None)
                else:
                    os.environ["KICAD9_SYMBOL_DIR"] = original_env


if __name__ == "__main__":
    unittest.main()

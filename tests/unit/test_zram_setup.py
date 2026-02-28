#!/usr/bin/python3
"""
Unit tests for python3/cinnamon/zram_setup.py

Run with:
    python3 -m unittest tests/unit/test_zram_setup.py
"""

import math
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, mock_open

# ---------------------------------------------------------------------------
# Bootstrap: load zram_setup without triggering the real cinnamon __init__.py
# (which has heavy optional dependencies like PIL and gi).
# This mirrors the bootstrap pattern used in test_file_handler.py.
# ---------------------------------------------------------------------------

import importlib.util as _ilu
import types as _types

_repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_repo_root, "python3"))

_cinnamon_pkg = _types.ModuleType("cinnamon")
_cinnamon_pkg.__path__ = [os.path.join(_repo_root, "python3", "cinnamon")]
_cinnamon_pkg.__package__ = "cinnamon"
sys.modules.setdefault("cinnamon", _cinnamon_pkg)

_spec = _ilu.spec_from_file_location(
    "cinnamon.zram_setup",
    os.path.join(_repo_root, "python3", "cinnamon", "zram_setup.py"),
)
zram_setup = _ilu.module_from_spec(_spec)
sys.modules["cinnamon.zram_setup"] = zram_setup
_cinnamon_pkg.zram_setup = zram_setup
_spec.loader.exec_module(zram_setup)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_meminfo(mem_total_kb):
    """Return a minimal /proc/meminfo string with the given MemTotal in kB."""
    return (
        "MemTotal:       {} kB\n"
        "MemFree:        1234567 kB\n"
        "MemAvailable:   9876543 kB\n"
    ).format(mem_total_kb)


# ---------------------------------------------------------------------------
# TestReadMemTotalMb
# ---------------------------------------------------------------------------

class TestReadMemTotalMb(unittest.TestCase):

    def _write_tmp(self, content):
        fd, path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(fd, "w") as fh:
            fh.write(content)
        return path

    def test_typical_8gb(self):
        # 8 GiB = 8388608 kB → 8192 MiB
        path = self._write_tmp(_fake_meminfo(8388608))
        try:
            self.assertEqual(zram_setup.read_mem_total_mb(path), 8192)
        finally:
            os.unlink(path)

    def test_typical_4gb(self):
        # 4 GiB = 4194304 kB → 4096 MiB
        path = self._write_tmp(_fake_meminfo(4194304))
        try:
            self.assertEqual(zram_setup.read_mem_total_mb(path), 4096)
        finally:
            os.unlink(path)

    def test_typical_16gb(self):
        # 16 GiB = 16777216 kB → 16384 MiB
        path = self._write_tmp(_fake_meminfo(16777216))
        try:
            self.assertEqual(zram_setup.read_mem_total_mb(path), 16384)
        finally:
            os.unlink(path)

    def test_2gb(self):
        # 2 GiB = 2097152 kB → 2048 MiB
        path = self._write_tmp(_fake_meminfo(2097152))
        try:
            self.assertEqual(zram_setup.read_mem_total_mb(path), 2048)
        finally:
            os.unlink(path)

    def test_rounds_down_on_odd_kb(self):
        # 1025 kB → 1 MiB (integer division 1025 // 1024 = 1)
        path = self._write_tmp(_fake_meminfo(1025))
        try:
            self.assertEqual(zram_setup.read_mem_total_mb(path), 1)
        finally:
            os.unlink(path)

    def test_file_not_found_raises_oserror(self):
        with self.assertRaises(OSError):
            zram_setup.read_mem_total_mb("/nonexistent/proc/meminfo")

    def test_missing_mem_total_raises_value_error(self):
        path = self._write_tmp("MemFree:        12345 kB\n")
        try:
            with self.assertRaises(ValueError):
                zram_setup.read_mem_total_mb(path)
        finally:
            os.unlink(path)

    def test_malformed_mem_total_raises_value_error(self):
        # Line starts with "MemTotal:" but has no value token.
        path = self._write_tmp("MemTotal:\n")
        try:
            with self.assertRaises(ValueError):
                zram_setup.read_mem_total_mb(path)
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# TestCalcZramSizeMb
# ---------------------------------------------------------------------------

class TestCalcZramSizeMb(unittest.TestCase):

    # --- Low-RAM branch (≤ 4096 MiB → ×2) ---

    def test_1gb_doubles(self):
        self.assertEqual(zram_setup.calc_zram_size_mb(1024), 2048)

    def test_2gb_doubles(self):
        self.assertEqual(zram_setup.calc_zram_size_mb(2048), 4096)

    def test_4gb_boundary_doubles(self):
        # Exactly at boundary: ≤ 4096 → ×2
        self.assertEqual(zram_setup.calc_zram_size_mb(4096), 8192)

    # --- Mid-RAM branch (4097–8192 MiB → ×1) ---

    def test_just_above_low_boundary(self):
        self.assertEqual(zram_setup.calc_zram_size_mb(4097), 4097)

    def test_6gb(self):
        self.assertEqual(zram_setup.calc_zram_size_mb(6144), 6144)

    def test_8gb_boundary_unchanged(self):
        # Exactly at upper mid boundary: ≤ 8192 → ×1
        self.assertEqual(zram_setup.calc_zram_size_mb(8192), 8192)

    # --- High-RAM branch (> 8192 MiB → ×0.5, rounded up) ---

    def test_just_above_mid_boundary(self):
        # 8193 × 0.5 = 4096.5 → ceil = 4097
        self.assertEqual(zram_setup.calc_zram_size_mb(8193), 4097)

    def test_16gb_halved(self):
        # 16384 × 0.5 = 8192 exactly
        self.assertEqual(zram_setup.calc_zram_size_mb(16384), 8192)

    def test_32gb_halved(self):
        self.assertEqual(zram_setup.calc_zram_size_mb(32768), 16384)

    def test_odd_high_ram_rounds_up(self):
        # 9001 × 0.5 = 4500.5 → ceil = 4501
        self.assertEqual(zram_setup.calc_zram_size_mb(9001), math.ceil(9001 * 0.5))

    # --- Error cases ---

    def test_zero_raises_value_error(self):
        with self.assertRaises(ValueError):
            zram_setup.calc_zram_size_mb(0)

    def test_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            zram_setup.calc_zram_size_mb(-1)


# ---------------------------------------------------------------------------
# TestGenerateZramConf
# ---------------------------------------------------------------------------

class TestGenerateZramConf(unittest.TestCase):

    def _conf(self, size=4096):
        return zram_setup.generate_zram_conf(size)

    def test_contains_zram0_section(self):
        self.assertIn("[zram0]", self._conf())

    def test_contains_zram_size_line(self):
        conf = self._conf(4096)
        self.assertIn("zram-size = 4096", conf)

    def test_contains_compression_algorithm(self):
        self.assertIn("compression-algorithm = zstd", self._conf())

    def test_size_value_appears_correctly(self):
        for size in (2048, 4096, 8192, 16384):
            conf = zram_setup.generate_zram_conf(size)
            self.assertIn("zram-size = {}".format(size), conf)

    def test_returns_string(self):
        self.assertIsInstance(self._conf(), str)

    def test_ends_with_newline(self):
        # Good practice: config files should end with a newline
        self.assertTrue(self._conf().endswith("\n"))


# ---------------------------------------------------------------------------
# TestInstallZramConf
# ---------------------------------------------------------------------------

class TestInstallZramConf(unittest.TestCase):

    def test_writes_file_in_correct_location(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_meminfo = os.path.join(tmpdir, "meminfo")
            with open(fake_meminfo, "w") as fh:
                fh.write(_fake_meminfo(4194304))  # 4096 MiB
            conf_path = zram_setup.install_zram_conf(tmpdir, proc_meminfo_path=fake_meminfo)
            expected = os.path.join(tmpdir, "etc", "systemd", "zram-generator.conf")
            self.assertEqual(conf_path, expected)
            self.assertTrue(os.path.isfile(expected))

    def test_config_content_correct_for_4gb(self):
        # 4096 MiB → ZRAM = 8192 MiB
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_meminfo = os.path.join(tmpdir, "meminfo")
            with open(fake_meminfo, "w") as fh:
                fh.write(_fake_meminfo(4194304))  # 4096 MiB
            conf_path = zram_setup.install_zram_conf(tmpdir, proc_meminfo_path=fake_meminfo)
            with open(conf_path, "r") as fh:
                content = fh.read()
        self.assertIn("[zram0]", content)
        self.assertIn("zram-size = 8192", content)
        self.assertIn("compression-algorithm = zstd", content)

    def test_config_content_correct_for_16gb(self):
        # 16384 MiB → ZRAM = 8192 MiB (×0.5)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_meminfo = os.path.join(tmpdir, "meminfo")
            with open(fake_meminfo, "w") as fh:
                fh.write(_fake_meminfo(16777216))  # 16384 MiB
            conf_path = zram_setup.install_zram_conf(tmpdir, proc_meminfo_path=fake_meminfo)
            with open(conf_path, "r") as fh:
                content = fh.read()
        self.assertIn("zram-size = 8192", content)

    def test_creates_missing_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # etc/systemd does not exist yet
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "etc")))
            fake_meminfo = os.path.join(tmpdir, "meminfo")
            with open(fake_meminfo, "w") as fh:
                fh.write(_fake_meminfo(8388608))  # 8192 MiB
            zram_setup.install_zram_conf(tmpdir, proc_meminfo_path=fake_meminfo)
            self.assertTrue(
                os.path.isdir(os.path.join(tmpdir, "etc", "systemd"))
            )

    def test_returns_path_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_meminfo = os.path.join(tmpdir, "meminfo")
            with open(fake_meminfo, "w") as fh:
                fh.write(_fake_meminfo(2097152))  # 2048 MiB
            result = zram_setup.install_zram_conf(tmpdir, proc_meminfo_path=fake_meminfo)
        self.assertIsInstance(result, str)

    def test_bad_meminfo_path_raises_oserror(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(OSError):
                zram_setup.install_zram_conf(
                    tmpdir, proc_meminfo_path="/nonexistent/proc/meminfo"
                )


if __name__ == "__main__":
    unittest.main()

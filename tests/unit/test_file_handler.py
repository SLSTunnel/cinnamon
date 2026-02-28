#!/usr/bin/python3
"""
Unit tests for python3/cinnamon/file_handler.py

Run with:
    python3 -m unittest tests/unit/test_file_handler.py
"""

import os
import sys
import struct
import tempfile
import unittest
from unittest.mock import patch

# Make the source tree importable when running from the repository root
_repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_repo_root, "python3"))

# Import file_handler directly to avoid triggering __init__.py which has
# optional system-level dependencies (PIL, gi, etc.) not needed for these tests.
import importlib.util as _ilu
import types as _types

# Register a stub 'cinnamon' package so patch() can resolve 'cinnamon.file_handler.*'
# without triggering the real __init__.py (which requires PIL / gi).
_cinnamon_pkg = _types.ModuleType("cinnamon")
_cinnamon_pkg.__path__ = [os.path.join(_repo_root, "python3", "cinnamon")]
_cinnamon_pkg.__package__ = "cinnamon"
sys.modules.setdefault("cinnamon", _cinnamon_pkg)

_spec = _ilu.spec_from_file_location(
    "cinnamon.file_handler",
    os.path.join(_repo_root, "python3", "cinnamon", "file_handler.py"),
)
file_handler = _ilu.module_from_spec(_spec)
sys.modules["cinnamon.file_handler"] = file_handler
_cinnamon_pkg.file_handler = file_handler
_spec.loader.exec_module(file_handler)


class TestDetectByExtension(unittest.TestCase):
    def test_exe_lowercase(self):
        self.assertEqual(file_handler.detect_by_extension("foo.exe"), ".exe")

    def test_exe_uppercase(self):
        self.assertEqual(file_handler.detect_by_extension("FOO.EXE"), ".exe")

    def test_apk(self):
        self.assertEqual(file_handler.detect_by_extension("app.apk"), ".apk")

    def test_ipa(self):
        self.assertEqual(file_handler.detect_by_extension("app.ipa"), ".ipa")

    def test_unsupported_extension(self):
        self.assertIsNone(file_handler.detect_by_extension("document.pdf"))

    def test_no_extension(self):
        self.assertIsNone(file_handler.detect_by_extension("script"))

    def test_path_with_directory(self):
        self.assertEqual(
            file_handler.detect_by_extension("/home/user/Downloads/game.exe"), ".exe"
        )


class TestVerifyMagic(unittest.TestCase):
    def _write_tmp(self, content):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        return path

    def test_exe_valid_magic(self):
        path = self._write_tmp(b"MZ\x90\x00extra bytes")
        try:
            self.assertTrue(file_handler.verify_magic(path, ".exe"))
        finally:
            os.unlink(path)

    def test_exe_invalid_magic(self):
        path = self._write_tmp(b"PK\x03\x04extra")
        try:
            self.assertFalse(file_handler.verify_magic(path, ".exe"))
        finally:
            os.unlink(path)

    def test_apk_valid_magic(self):
        path = self._write_tmp(b"PK\x03\x04extra bytes")
        try:
            self.assertTrue(file_handler.verify_magic(path, ".apk"))
        finally:
            os.unlink(path)

    def test_apk_invalid_magic(self):
        path = self._write_tmp(b"MZ\x90\x00extra")
        try:
            self.assertFalse(file_handler.verify_magic(path, ".apk"))
        finally:
            os.unlink(path)

    def test_ipa_valid_magic(self):
        path = self._write_tmp(b"PK\x03\x04extra bytes")
        try:
            self.assertTrue(file_handler.verify_magic(path, ".ipa"))
        finally:
            os.unlink(path)

    def test_nonexistent_file_returns_true(self):
        # Missing file should not crash the caller; returns True so dispatch proceeds
        self.assertTrue(file_handler.verify_magic("/nonexistent/path.exe", ".exe"))


class TestCheckTool(unittest.TestCase):
    def test_finds_existing_tool(self):
        # 'python3' is definitely on PATH in this environment
        self.assertTrue(file_handler.check_tool("python3"))

    def test_missing_tool(self):
        self.assertFalse(file_handler.check_tool("__tool_that_does_not_exist__"))


class TestWineAvailable(unittest.TestCase):
    @patch("cinnamon.file_handler.check_tool")
    def test_wine_present(self, mock_check):
        mock_check.side_effect = lambda name: name == "wine"
        self.assertTrue(file_handler.wine_available())

    @patch("cinnamon.file_handler.check_tool")
    def test_proton_present(self, mock_check):
        mock_check.side_effect = lambda name: name == "proton"
        self.assertTrue(file_handler.wine_available())

    @patch("cinnamon.file_handler.check_tool", return_value=False)
    def test_neither_present(self, _mock):
        self.assertFalse(file_handler.wine_available())


class TestAdbAvailable(unittest.TestCase):
    @patch("cinnamon.file_handler.check_tool")
    def test_adb_present(self, mock_check):
        mock_check.side_effect = lambda name: name == "adb"
        self.assertTrue(file_handler.adb_available())

    @patch("cinnamon.file_handler.check_tool", return_value=False)
    def test_adb_absent(self, _mock):
        self.assertFalse(file_handler.adb_available())


class TestDetectPackageManager(unittest.TestCase):
    @patch("cinnamon.file_handler.check_tool")
    def test_apt_get_detected(self, mock_check):
        mock_check.side_effect = lambda name: name == "apt-get"
        result = file_handler.detect_package_manager()
        self.assertIsNotNone(result)
        pm_key, base_argv = result
        self.assertEqual(pm_key, "apt-get")
        self.assertIn("apt-get", base_argv)
        self.assertIn("pkexec", base_argv)

    @patch("cinnamon.file_handler.check_tool")
    def test_dnf_detected(self, mock_check):
        mock_check.side_effect = lambda name: name == "dnf"
        result = file_handler.detect_package_manager()
        self.assertIsNotNone(result)
        pm_key, _ = result
        self.assertEqual(pm_key, "dnf")

    @patch("cinnamon.file_handler.check_tool")
    def test_pacman_detected(self, mock_check):
        mock_check.side_effect = lambda name: name == "pacman"
        result = file_handler.detect_package_manager()
        self.assertIsNotNone(result)
        pm_key, _ = result
        self.assertEqual(pm_key, "pacman")

    @patch("cinnamon.file_handler.check_tool")
    def test_zypper_detected(self, mock_check):
        mock_check.side_effect = lambda name: name == "zypper"
        result = file_handler.detect_package_manager()
        self.assertIsNotNone(result)
        pm_key, _ = result
        self.assertEqual(pm_key, "zypper")

    @patch("cinnamon.file_handler.check_tool", return_value=False)
    def test_none_when_no_pm(self, _mock):
        self.assertIsNone(file_handler.detect_package_manager())

    @patch("cinnamon.file_handler.check_tool")
    def test_apt_preferred_over_dnf(self, mock_check):
        # apt-get comes first in the list; both present -> apt-get wins
        mock_check.side_effect = lambda name: name in ("apt-get", "dnf")
        pm_key, base_argv = file_handler.detect_package_manager()
        self.assertEqual(pm_key, "apt-get")
        self.assertIn("apt-get", base_argv)


class TestBuildInstallArgv(unittest.TestCase):
    @patch("cinnamon.file_handler.detect_package_manager",
           return_value=("apt-get", ["pkexec", "apt-get", "install", "-y"]))
    def test_wine_on_apt(self, _mock):
        argv = file_handler.build_install_argv("wine")
        self.assertEqual(argv, ["pkexec", "apt-get", "install", "-y", "wine"])

    @patch("cinnamon.file_handler.detect_package_manager",
           return_value=("dnf", ["pkexec", "dnf", "install", "-y"]))
    def test_adb_on_dnf(self, _mock):
        argv = file_handler.build_install_argv("adb")
        self.assertEqual(argv, ["pkexec", "dnf", "install", "-y", "android-tools"])

    @patch("cinnamon.file_handler.detect_package_manager",
           return_value=("pacman", ["pkexec", "pacman", "-S", "--noconfirm"]))
    def test_adb_on_pacman(self, _mock):
        argv = file_handler.build_install_argv("adb")
        self.assertEqual(argv, ["pkexec", "pacman", "-S", "--noconfirm", "android-tools"])

    @patch("cinnamon.file_handler.detect_package_manager", return_value=None)
    def test_returns_none_when_no_pm(self, _mock):
        self.assertIsNone(file_handler.build_install_argv("wine"))

    @patch("cinnamon.file_handler.detect_package_manager",
           return_value=("apt-get", ["pkexec", "apt-get", "install", "-y"]))
    def test_unknown_tool_returns_none(self, _mock):
        self.assertIsNone(file_handler.build_install_argv("unknown_tool"))


class TestHandleExe(unittest.TestCase):
    @patch("cinnamon.file_handler.wine_available", return_value=True)
    @patch("cinnamon.file_handler.check_tool")
    def test_wine_present_action(self, mock_check, _mock_wine):
        mock_check.side_effect = lambda name: name == "wine"
        result = file_handler.handle_exe("/tmp/setup.exe")
        self.assertEqual(result["action"], "run_with_wine")
        self.assertEqual(result["tool"], "wine")
        self.assertEqual(result["argv"][0], "wine")
        self.assertTrue(result["wine_available"])
        self.assertEqual(result["auto_install_argv"], [])

    @patch("cinnamon.file_handler.wine_available", return_value=True)
    @patch("cinnamon.file_handler.check_tool")
    def test_proton_preferred_over_wine(self, mock_check, _mock_wine):
        mock_check.side_effect = lambda name: name == "proton"
        result = file_handler.handle_exe("/tmp/setup.exe")
        self.assertEqual(result["tool"], "proton")

    @patch("cinnamon.file_handler.wine_available", return_value=False)
    @patch("cinnamon.file_handler.build_install_argv", return_value=["pkexec", "apt-get", "install", "-y", "wine"])
    def test_wine_absent_auto_install_argv(self, _mock_build, _mock_wine):
        result = file_handler.handle_exe("/tmp/setup.exe")
        self.assertEqual(result["action"], "install_wine")
        self.assertFalse(result["wine_available"])
        self.assertEqual(result["argv"], [])
        self.assertEqual(result["auto_install_argv"], ["pkexec", "apt-get", "install", "-y", "wine"])

    @patch("cinnamon.file_handler.wine_available", return_value=False)
    @patch("cinnamon.file_handler.build_install_argv", return_value=None)
    def test_wine_absent_no_pm_empty_install_argv(self, _mock_build, _mock_wine):
        result = file_handler.handle_exe("/tmp/setup.exe")
        self.assertEqual(result["auto_install_argv"], [])

    def test_notify_fn_called(self):
        notifications = []
        with patch("cinnamon.file_handler.wine_available", return_value=False), \
            patch("cinnamon.file_handler.build_install_argv", return_value=None):
            file_handler.handle_exe("/tmp/setup.exe", _notify_fn=lambda t, b: notifications.append((t, b)))
        self.assertEqual(len(notifications), 1)


class TestHandleApk(unittest.TestCase):
    @patch("cinnamon.file_handler.adb_available", return_value=True)
    def test_adb_present_action(self, _mock):
        result = file_handler.handle_apk("/tmp/app.apk")
        self.assertEqual(result["action"], "adb_install")
        self.assertIn("adb", result["argv"])
        self.assertIn("install", result["argv"])
        self.assertEqual(result["auto_install_argv"], [])

    @patch("cinnamon.file_handler.adb_available", return_value=False)
    @patch("cinnamon.file_handler.build_install_argv", return_value=["pkexec", "apt-get", "install", "-y", "adb"])
    def test_adb_absent_auto_install_argv(self, _mock_build, _mock_adb):
        result = file_handler.handle_apk("/tmp/app.apk")
        self.assertEqual(result["action"], "install_adb")
        self.assertEqual(result["argv"], [])
        self.assertEqual(result["auto_install_argv"], ["pkexec", "apt-get", "install", "-y", "adb"])

    @patch("cinnamon.file_handler.adb_available", return_value=False)
    @patch("cinnamon.file_handler.build_install_argv", return_value=None)
    def test_adb_absent_no_pm_empty_install_argv(self, _mock_build, _mock_adb):
        result = file_handler.handle_apk("/tmp/app.apk")
        self.assertEqual(result["auto_install_argv"], [])

    def test_notify_fn_called(self):
        notifications = []
        with patch("cinnamon.file_handler.adb_available", return_value=False), \
            patch("cinnamon.file_handler.build_install_argv", return_value=None):
            file_handler.handle_apk("/tmp/app.apk", _notify_fn=lambda t, b: notifications.append((t, b)))
        self.assertEqual(len(notifications), 1)


class TestHandleIpa(unittest.TestCase):
    def test_action_is_inspect_only(self):
        result = file_handler.handle_ipa("/nonexistent/app.ipa")
        self.assertEqual(result["action"], "inspect_only")
        self.assertEqual(result["argv"], [])

    def test_message_contains_ios_warning(self):
        result = file_handler.handle_ipa("/nonexistent/app.ipa")
        self.assertIn("iOS", result["message"])
        self.assertIn("cannot be installed", result["message"])

    def test_notify_fn_called(self):
        notifications = []
        file_handler.handle_ipa("/nonexistent/app.ipa", _notify_fn=lambda t, b: notifications.append((t, b)))
        self.assertEqual(len(notifications), 1)


class TestDispatch(unittest.TestCase):
    def test_dispatch_exe(self):
        with patch("cinnamon.file_handler.verify_magic", return_value=True), \
            patch("cinnamon.file_handler.wine_available", return_value=False), \
            patch("cinnamon.file_handler.build_install_argv", return_value=None):
            result = file_handler.dispatch("/tmp/program.exe")
        self.assertIsNotNone(result)
        self.assertEqual(result["ext"], ".exe")

    def test_dispatch_apk(self):
        with patch("cinnamon.file_handler.verify_magic", return_value=True), \
            patch("cinnamon.file_handler.adb_available", return_value=False), \
            patch("cinnamon.file_handler.build_install_argv", return_value=None):
            result = file_handler.dispatch("/tmp/app.apk")
        self.assertIsNotNone(result)
        self.assertEqual(result["ext"], ".apk")

    def test_dispatch_ipa(self):
        with patch("cinnamon.file_handler.verify_magic", return_value=True):
            result = file_handler.dispatch("/tmp/app.ipa")
        self.assertIsNotNone(result)
        self.assertEqual(result["ext"], ".ipa")

    def test_dispatch_unsupported_returns_none(self):
        result = file_handler.dispatch("/tmp/document.pdf")
        self.assertIsNone(result)

    def test_dispatch_magic_mismatch_still_dispatches(self):
        """Magic mismatch should log a warning but still call the handler."""
        with patch("cinnamon.file_handler.verify_magic", return_value=False), \
            patch("cinnamon.file_handler.wine_available", return_value=False), \
            patch("cinnamon.file_handler.build_install_argv", return_value=None):
            result = file_handler.dispatch("/tmp/fake.exe")
        self.assertIsNotNone(result)

    def test_dispatch_result_has_auto_install_argv_key(self):
        with patch("cinnamon.file_handler.verify_magic", return_value=True), \
            patch("cinnamon.file_handler.wine_available", return_value=False), \
            patch("cinnamon.file_handler.build_install_argv", return_value=["pkexec", "apt-get", "install", "-y", "wine"]):
            result = file_handler.dispatch("/tmp/program.exe")
        self.assertIn("auto_install_argv", result)
        self.assertEqual(result["auto_install_argv"], ["pkexec", "apt-get", "install", "-y", "wine"])


if __name__ == "__main__":
    unittest.main()

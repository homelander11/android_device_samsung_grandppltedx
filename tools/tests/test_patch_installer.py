"""Exercise multi-repository preflight, repeat application, and rollback."""
import contextlib
import difflib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "patch_installer", Path(__file__).resolve().parents[1] / "apply_android11_patches.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class PatchInstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="grandppltedx-patch-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = self.root / "sources"
        self.patches = self.root / "patches"
        self.components = ("hardware/interfaces", "system/bt")
        for component in self.components:
            repo = self.sources / component
            repo.mkdir(parents=True)
            subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
            (repo / "sample.txt").write_text("old\n")
            folder = self.patches / component
            folder.mkdir(parents=True)
            diff = "".join(difflib.unified_diff(
                ["old\n"], ["new\n"], fromfile="a/sample.txt", tofile="b/sample.txt"))
            (folder / "001.patch").write_text(diff)

    def invoke(self, mode):
        with patch.object(installer, "PATCHES", self.patches), patch.object(
                sys, "argv", ["patch-installer", "--source-root", str(self.sources), mode]), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return installer.main()

    def contents(self):
        return [(self.sources / name / "sample.txt").read_text()
                for name in self.components]

    def test_check_is_read_only_and_apply_is_idempotent(self):
        self.assertEqual(self.invoke("--check"), 0)
        self.assertEqual(self.contents(), ["old\n", "old\n"])
        self.assertEqual(self.invoke("--apply"), 0)
        self.assertEqual(self.contents(), ["new\n", "new\n"])
        self.assertEqual(self.invoke("--apply"), 0)
        self.assertEqual(self.contents(), ["new\n", "new\n"])

    def test_one_bad_component_prevents_all_mutations(self):
        (self.sources / "system/bt/sample.txt").write_text("user changes\n")
        self.assertEqual(self.invoke("--apply"), 1)
        self.assertEqual(self.contents(), ["old\n", "user changes\n"])

    def test_apply_failure_reverses_only_this_runs_patches(self):
        real_run = installer.run

        def fail_second_apply(repo, *args):
            if repo == (self.sources / "system/bt").resolve() and len(args) == 1:
                return subprocess.CompletedProcess(args, 1, "", "injected apply failure")
            return real_run(repo, *args)

        with patch.object(installer, "run", side_effect=fail_second_apply):
            self.assertEqual(self.invoke("--apply"), 1)
        self.assertEqual(self.contents(), ["old\n", "old\n"])

    def test_parent_repository_cannot_silently_skip_component_paths(self):
        # Give the component an ordinary directory inside a parent checkout.
        # Use a fresh root so the initialized component repos remain untouched.
        other = self.root / "parent-checkout"
        for name in self.components:
            (other / name).mkdir(parents=True)
        subprocess.run(["git", "-C", str(other), "init", "-q"], check=True)
        self.sources = other
        self.assertEqual(self.invoke("--check"), 1)


if __name__ == "__main__":
    unittest.main()

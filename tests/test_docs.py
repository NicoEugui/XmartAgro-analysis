"""The team document must not rot: every file or folder it names exists, and the commands it gives are commands of the tool."""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "como-funciona.md"


class TeamDocument(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")

    def test_every_path_it_names_exists(self):
        names = re.findall(r"`((?:src|tests|schema|docs|reports)/[^`\s]*)`", self.text)
        self.assertGreater(len(names), 30)
        for name in names:
            found = list(REPO.glob(name)) if "*" in name else [REPO / name]
            self.assertTrue(found and all(p.exists() for p in found), name)

    def test_every_command_it_gives_is_a_subcommand_of_the_tool(self):
        from xmart_analysis import cli
        import argparse
        import contextlib
        import io
        wanted = set(re.findall(r"`xmart-analysis ([a-z-]+)", self.text))
        parser_text = io.StringIO()
        with contextlib.redirect_stdout(parser_text), contextlib.suppress(SystemExit):
            cli.main(["--help"])
        for command in wanted:
            self.assertIn(command, parser_text.getvalue(), command)
        self.assertTrue({"run", "export", "validate", "report", "calibrate", "ingest", "learn"} <= wanted)
        self.assertIsNotNone(argparse)

    def test_it_says_what_is_simulated_and_that_the_pipeline_is_not_connected(self):
        self.assertIn("simulated: True", self.text)
        self.assertIn("Lo que falta para conectar todo", self.text)
        self.assertIn("Qué es real y qué es simulado", self.text)


if __name__ == "__main__":
    unittest.main()

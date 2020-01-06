"""Test ``click_from_docstring``."""

import click_from_docstring as tscr
import pytest
# from unittest import mock
# import click
from click import testing as click_testing


class TestSpam:
    @pytest.fixture
    def context_settings(self):
        return {"help_option_names": ["-h", "--help"]}

    @pytest.fixture
    def command(self, context_settings):
        @tscr.command(context_settings=context_settings)
        def spam(eggs: str, count: int = 2):
            """Print spam.

            Uses a can of spam to count eggs.

            Args:
                eggs: to go with your spam
                count: number of eggs
            """

            for j in range(count):
                print("spam", eggs)
        return spam

    @pytest.fixture
    def runner(self):
        return click_testing.CliRunner()

    def test_help(self, runner, command):
        res = runner.invoke(command, ["beans", "--help"])
        assert not res.exit_code
        assert res.stdout == (
            "Usage: spam [OPTIONS] EGGS\n"
            "\n"
            "  Print spam.\n"
            "\n"
            "  Uses a can of spam to count eggs.\n"
            "\n"
            "Options:\n"
            "  --count INTEGER  number of eggs\n"
            "  -h, --help       Show this message and exit.\n"
        )

    def test_no_optionals(self, runner, command):
        res = runner.invoke(command, ["beans"])
        assert not res.exit_code
        assert res.stdout == "spam beans\nspam beans\n"

    def test_count(self, runner, command):
        res = runner.invoke(command, ["beans", "--count", "3"])
        assert not res.exit_code
        assert res.stdout == "spam beans\nspam beans\nspam beans\n"

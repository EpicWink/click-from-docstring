"""Test ``click_from_docstring``."""

import click_from_docstring as tscr
import pytest
# from unittest import mock
from click import testing as click_testing
import math
import typing as t
import datetime
import uuid


class TestSpam:
    @pytest.fixture
    def context_settings(self):
        """``click`` context settings."""
        return {"help_option_names": ["-h", "--help"]}

    @pytest.fixture
    def _cmd0(self, context_settings):
        """With type annotations."""
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
    def _cmd1(self, context_settings):
        """With types in docstring."""
        @tscr.command(context_settings=context_settings)
        def spam(eggs, count=2):
            """Print spam.

            Uses a can of spam to count eggs.

            Args:
                eggs (str): to go with your spam
                count (int): number of eggs
            """

            for j in range(count):
                print("spam", eggs)
        return spam

    @pytest.fixture(params=[pytest.param(j, id="cmd%d" % j) for j in range(2)])
    def command(self, request, _cmd0, _cmd1):
        """An example command with one required and one optional param."""
        return [_cmd0, _cmd1][request.param]

    @pytest.fixture
    def runner(self):
        """``click`` CLI test runner."""
        return click_testing.CliRunner()

    @pytest.mark.parametrize("help_flag", ["--help", "-h"])
    def test_help(self, runner, command, help_flag):
        res = runner.invoke(command, ["beans", help_flag])
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

    def test_option(self, runner, command):
        res = runner.invoke(command, ["beans", "--count", "3"])
        assert not res.exit_code
        assert res.stdout == "spam beans\nspam beans\nspam beans\n"

    def test_option_invalid(self, runner, command):
        res = runner.invoke(command, ["beans", "--count", "spam"])
        assert res.exit_code == 2


class TestProd:
    @pytest.fixture
    def _cmd0(self):
        @tscr.command()
        def my_prod(values: t.List[float]):
            """Take product of floats.

            Args:
                values: values to multiply
            """

            prod = 1.0
            for value in values:
                prod *= value
            print(prod)
        return my_prod

    @pytest.fixture
    def _cmd1(self):
        @tscr.command()
        def my_prod(*values: float):
            """Take product of floats.

            Args:
                values: values to multiply
            """

            prod = 1.0
            for value in values:
                prod *= value
            print(prod)
        return my_prod

    @pytest.fixture
    def _cmd2(self):
        @tscr.command()
        def my_prod(values):
            """Take product of floats.

            Args:
                values (list[float]): values to multiply
            """

            prod = 1.0
            for value in values:
                prod *= value
            print(prod)
        return my_prod

    @pytest.fixture
    def _cmd3(self):
        @tscr.command()
        def my_prod(*values):
            """Take product of floats.

            Args:
                values (float): values to multiply
            """

            prod = 1.0
            for value in values:
                prod *= value
            print(prod)
        return my_prod

    @pytest.fixture(params=[pytest.param(j, id="cmd%d" % j) for j in range(4)])
    def command(self, request, _cmd0, _cmd1, _cmd2, _cmd3):
        """An example product command."""
        return [_cmd0, _cmd1, _cmd2, _cmd3][request.param]

    @pytest.fixture
    def runner(self):
        """``click`` CLI test runner."""
        return click_testing.CliRunner()

    def test_help(self, runner, command):
        res = runner.invoke(command, ["--help"])
        assert not res.exit_code
        assert res.stdout == (
            "Usage: my-prod [OPTIONS] [VALUES]...\n"
            "\n"
            "  Take product of floats.\n"
            "\n"
            "Options:\n"
            "  --help  Show this message and exit.\n"
        )

    def test_var_args(self, runner, command):
        res = runner.invoke(command, ["42.0", "3", "2.2"])
        assert not res.exit_code
        assert float(res.stdout) == pytest.approx(277.2)

    def test_inf(self, runner, command):
        res = runner.invoke(command, ["42.0", "inf"])
        assert not res.exit_code
        assert float(res.stdout) == math.inf

    def test_nan(self, runner, command):
        res = runner.invoke(command, ["42.0", "nan"])
        assert not res.exit_code
        assert math.isnan(float(res.stdout))

    def test_value_invalid(self, runner, command):
        res = runner.invoke(command, ["42.0", "spam"])
        assert res.exit_code == 2


class TestDateTime:
    @pytest.fixture
    def _cmd0(self):
        @tscr.command()
        def count_days(since: datetime.datetime):
            """Counts days since a date.

            Args:
                since: date to counts days from
            """

            now = datetime.datetime.utcnow()
            delta = now - since
            print(delta.days)
        return count_days

    @pytest.fixture
    def _cmd1(self):
        @tscr.command()
        def count_days(since):
            """Counts days since a date.

            Args:
                since (datetime.datetime): date to counts days from
            """

            now = datetime.datetime.utcnow()
            delta = now - since
            print(delta.days)
        return count_days

    @pytest.fixture(params=[pytest.param(j, id="cmd%d" % j) for j in range(2)])
    def command(self, request, _cmd0, _cmd1):
        """An example date-time command."""
        return [_cmd0, _cmd1][request.param]

    @pytest.fixture
    def runner(self):
        """``click`` CLI test runner."""
        return click_testing.CliRunner()

    def test_help(self, runner, command):
        res = runner.invoke(command, ["--help"])
        assert not res.exit_code
        assert res.stdout == (
            "Usage: count-days [OPTIONS] "
            "[%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]\n"
            "\n"
            "  Counts days since a date.\n"
            "\n"
            "Options:\n"
            "  --help  Show this message and exit.\n"
        )

    def test_date(self, runner, command):
        now = datetime.datetime.utcnow()
        dt = now - datetime.timedelta(days=3)
        date_str = dt.strftime("%Y-%m-%d")
        res = runner.invoke(command, [date_str])
        assert not res.exit_code
        assert float(res.stdout) == 3.0

    @pytest.mark.parametrize("sep", ["T", " "])
    def test_date_time(self, runner, command, sep):
        now = datetime.datetime.utcnow()
        dt = now - datetime.timedelta(days=3)
        date_str = dt.isoformat(sep=sep, timespec="seconds")
        res = runner.invoke(command, [date_str])
        print(res.stdout)
        assert not res.exit_code
        assert float(res.stdout) == 3.0


class TestUUID:
    @pytest.fixture
    def _cmd0(self):
        @tscr.command()
        def get_uuid_version(item_id: uuid.UUID):
            """Get version of a UUID.

            Args:
                item_id: given UUID
            """

            print(item_id.version)
        return get_uuid_version

    @pytest.fixture
    def _cmd1(self):
        @tscr.command()
        def get_uuid_version(item_id):
            """Get version of a UUID.

            Args:
                item_id (uuid.UUID): given UUID
            """

            print(item_id.version)
        return get_uuid_version

    @pytest.fixture(params=[pytest.param(j, id="cmd%d" % j) for j in range(2)])
    def command(self, request, _cmd0, _cmd1):
        """An example UUID command."""
        return [_cmd0, _cmd1][request.param]

    @pytest.fixture
    def runner(self):
        """``click`` CLI test runner."""
        return click_testing.CliRunner()

    def test_help(self, runner, command):
        res = runner.invoke(command, ["--help"])
        assert not res.exit_code
        assert res.stdout == (
            "Usage: get-uuid-version [OPTIONS] ITEM_ID\n"
            "\n"
            "  Get version of a UUID.\n"
            "\n"
            "Options:\n"
            "  --help  Show this message and exit.\n"
        )

    @pytest.mark.parametrize(
        ("item_id", "exp"),
        [
            pytest.param("c582c2ee-38d2-11ea-bf3d-37e10e5b7e34", 1, id="uuid1"),
            pytest.param("0ec38e35-7290-3411-a65d-cf556b9e4e0d", 3, id="uuid3"),
            pytest.param("bafd3899-1df5-4aea-b715-ac0ff839c592", 4, id="uuid4"),
            pytest.param("fa74f663-7681-5ad2-985f-72fb005f1425", 5, id="uuid5"),
        ],
    )
    def test(self, runner, command, item_id, exp):
        res = runner.invoke(command, [item_id])
        print(res.stdout)
        assert not res.exit_code
        assert int(res.stdout) == exp

import pytest

from pipeline.cli import build_parser, main


def test_sources_command_lists_every_dataset(capsys):
    assert main(["sources"]) == 0
    out = capsys.readouterr().out
    assert "cpi_monthly" in out
    assert "KAHRAMAA" in out


def test_unknown_command_exits_with_usage_error():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["nope"])
    assert exc.value.code == 2

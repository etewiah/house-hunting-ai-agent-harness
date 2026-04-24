from __future__ import annotations

from src.ui.cli import main


def test_bare_cli_explains_removed_interactive_search(capsys):
    main([])

    output = capsys.readouterr().out
    assert "usage: house-hunt" in output
    assert "Standalone interactive listing search has been removed" in output
    assert "Your brief:" not in output

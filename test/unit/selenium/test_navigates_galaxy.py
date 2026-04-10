from types import SimpleNamespace
from unittest.mock import MagicMock

from galaxy.selenium.navigates_galaxy import NavigatesGalaxy


def _make_masthead() -> SimpleNamespace:
    return SimpleNamespace(
        _=SimpleNamespace(wait_for_visible=MagicMock()),
        logged_in_only=SimpleNamespace(wait_for_visible=MagicMock()),
        login_masthead_button=SimpleNamespace(wait_for_present=MagicMock()),
    )


def test_wait_for_masthead_waits_for_logged_out_controls() -> None:
    masthead = _make_masthead()
    nav = SimpleNamespace(components=SimpleNamespace(masthead=masthead), is_logged_in=MagicMock(return_value=False))

    NavigatesGalaxy.wait_for_masthead(nav)

    masthead._.wait_for_visible.assert_called_once()
    masthead.login_masthead_button.wait_for_present.assert_called_once()
    masthead.logged_in_only.wait_for_visible.assert_not_called()


def test_wait_for_masthead_waits_for_logged_in_controls() -> None:
    masthead = _make_masthead()
    nav = SimpleNamespace(components=SimpleNamespace(masthead=masthead), is_logged_in=MagicMock(return_value=True))

    NavigatesGalaxy.wait_for_masthead(nav)

    masthead._.wait_for_visible.assert_called_once()
    masthead.logged_in_only.wait_for_visible.assert_called_once()
    masthead.login_masthead_button.wait_for_present.assert_not_called()

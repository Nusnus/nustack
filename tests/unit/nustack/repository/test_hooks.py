"""The hooks config yields every hook the check reads, or the reason it cannot."""

import pytest

from nustack.repository.config import InvalidConfigError
from nustack.repository.hooks import Hooks


class TestHooks:
    """The check sees each hook that could rewrite a file.

    A hook with no id is refused, naming where it sits.
    """

    def test_refuses_a_hook_with_no_id_naming_where_it_sits(self) -> None:
        with pytest.raises(InvalidConfigError) as caught:
            Hooks.parse(
                b"repos:\n  - hooks:\n      - exclude: x\n  - hooks:\n      - id: b\n"
            )
        assert str(caught.value) == "repos.0.hooks.0.id: add it"

    def test_lists_every_hook_of_every_repository(self) -> None:
        hooks = Hooks.parse(
            b"repos:\n  - hooks:\n      - id: a\n        exclude: x\n"
            b"  - hooks:\n      - id: b\n"
        )
        assert [(hook.id, hook.exclude) for hook in hooks.hooks] == [
            ("a", "x"),
            ("b", None),
        ]

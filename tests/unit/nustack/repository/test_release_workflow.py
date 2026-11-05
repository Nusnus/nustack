"""The release workflow reads down to the tags whose push starts it, or is refused."""

import pytest

from nustack.repository.config import InvalidConfigError
from nustack.repository.release_workflow import ReleaseWorkflow


class TestReleaseWorkflow:
    """A release workflow reads as the tag filters of its push trigger.

    With no push trigger, or a push trigger with no tags filter, it reads as no tags;
    `on` may name its events, a push trigger may be null, and one tags filter may
    be a string.
    An `on`, a push trigger or a tags filter of the wrong shape is refused, naming
    the field, and an `on` that `%YAML 1.1` reads as true is refused with the fix.
    """

    @pytest.mark.parametrize(
        ("content", "tags"),
        [
            (b'on:\n  push:\n    tags: ["v*", "w*"]\n', ("v*", "w*")),
            (b'on:\n  push:\n    tags: "v*"\n', ("v*",)),
            (b"on:\n  push:\n    branches: [main]\n", ()),
            (b"on:\n  push: {}\n", ()),
            (b"on:\n  workflow_dispatch:\n", ()),
            (b"on: {}\njobs: {}\n", ()),
            (b"on:\n  push:\n", ()),
            (b"on: push\njobs: {}\n", ()),
            (b"on: [push, workflow_dispatch]\njobs: {}\n", ()),
        ],
        ids=[
            "tags",
            "one-tag",
            "no-tags",
            "empty-push",
            "no-push",
            "empty-on",
            "null-push",
            "event",
            "events",
        ],
    )
    def test_reads_the_tags_whose_push_starts_it(
        self, content: bytes, tags: tuple[str, ...]
    ) -> None:
        assert ReleaseWorkflow.parse(content).on.push.tags == tags

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            (b"on:\n  push:\n    tags: [1]\n", "on.push.tags.0: make it a string"),
            (b"on:\n  push: 1\n", "on.push: make it an object of keys and values"),
            (b"on: 1\njobs: {}\n", "on: make it an object of keys and values"),
            (b"on: [1]\njobs: {}\n", "on: make it an object of keys and values"),
            (b"jobs: {}\n", "on: add it"),
            (
                b"%YAML 1.1\n---\non:\n  push:\n    tags: [v*]\n",
                (
                    "%YAML 1.1 reads its on key as true; drop the %YAML 1.1 directive,"
                    ' or quote the key as "on"'
                ),
            ),
        ],
        ids=["tag", "push", "on", "events", "no-on", "on-as-true"],
    )
    def test_refuses_a_trigger_of_the_wrong_shape(
        self, content: bytes, reason: str
    ) -> None:
        with pytest.raises(InvalidConfigError) as caught:
            ReleaseWorkflow.parse(content)
        assert str(caught.value) == reason

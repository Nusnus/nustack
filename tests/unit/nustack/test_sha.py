"""A commit's SHA holds Git's form only; text given as one reads only in that form."""

import pytest

from nustack.sha import NotSha1Error
from nustack.sha import Sha
from nustack.sha import ShaError


class TestSha:
    """A SHA is 40 lowercase hex digits, read back whole or as GitHub shortens it.

    One built from other text fails as a commit Git names by other than its SHA-1.
    Text holding 40 lowercase hex digits reads as a SHA; any other text fails with
    the fix.
    """

    def test_reads_back_whole_and_short(self) -> None:
        sha = Sha("81c986c0e0a7c511f2941ed3cec09f7975687f80")
        assert (str(sha), sha.short) == (
            "81c986c0e0a7c511f2941ed3cec09f7975687f80",
            "81c986c",
        )

    def test_refuses_to_build_from_other_text(self) -> None:
        with pytest.raises(NotSha1Error) as caught:
            Sha("81c986c")
        assert str(caught.value) == (
            "named a commit by other than its SHA-1; nustack reads only repositories"
            " whose commits Git names by SHA-1, so use one"
        )

    def test_reads_text_holding_one(self) -> None:
        assert Sha.parse("81c986c0e0a7c511f2941ed3cec09f7975687f80") == Sha(
            "81c986c0e0a7c511f2941ed3cec09f7975687f80"
        )

    @pytest.mark.parametrize(
        ("value", "what"),
        [
            (
                "81C986C0E0A7C511F2941ED3CEC09F7975687F80",
                (
                    "give the commit as its SHA, not"
                    " 81C986C0E0A7C511F2941ED3CEC09F7975687F80; use 40 lowercase hex"
                    " digits, such as 81c986c0e0a7c511f2941ed3cec09f7975687f80"
                ),
            ),
            (
                "HEAD",
                (
                    "give the commit as its SHA, not HEAD; use 40 lowercase hex"
                    " digits, such as 81c986c0e0a7c511f2941ed3cec09f7975687f80"
                ),
            ),
            (
                "81c986c",
                (
                    "give the commit as its SHA, not 81c986c; use 40 lowercase hex"
                    " digits, such as 81c986c0e0a7c511f2941ed3cec09f7975687f80"
                ),
            ),
            (
                "81c986c0e0a7c511f2941ed3cec09f7975687f80\n",
                (
                    "give the commit as its SHA, not"
                    " 81c986c0e0a7c511f2941ed3cec09f7975687f80\n; use 40 lowercase hex"
                    " digits, such as 81c986c0e0a7c511f2941ed3cec09f7975687f80"
                ),
            ),
        ],
    )
    def test_refuses_text_of_another_form(self, value: str, what: str) -> None:
        with pytest.raises(ShaError) as caught:
            Sha.parse(value)
        assert str(caught.value) == what

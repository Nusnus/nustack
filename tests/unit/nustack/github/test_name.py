"""A repository's name and URL read from text, and back in the forms GitHub writes.

Text of another form, or an owner or name GitHub would not take, is refused with the
fix, and a refused URL is never repeated.
"""

import pytest

from nustack.github.name import GitHubNameError
from nustack.github.name import NameWithOwner
from nustack.github.name import RepositoryUrl


class TestNameWithOwner:
    """A repository given as <owner>/<name> reads as both; any other form fails.

    So does an owner or name GitHub would not take. A name may start with a dot, such
    as .github, or be only dots, such as ..., other than . and ..; a managed user's
    owner ends in an underscore and its enterprise's short code. It reads back as
    <owner>/<name>. One built from an owner or name GitHub would not take fails too.
    """

    @pytest.mark.parametrize(("owner", "name"), [("", "r"), ("o", ""), ("-o", "r")])
    def test_refuses_to_build_from_an_owner_or_name_github_would_not_take(
        self, owner: str, name: str
    ) -> None:
        with pytest.raises(GitHubNameError) as caught:
            NameWithOwner(owner, name)
        assert str(caught.value) == (
            "give the repository as GitHub names it; for <owner>, use letters, digits"
            " and single hyphens, with no hyphen first or last, such as Nusnus, and for"
            " a managed user an underscore and its enterprise's short code at the end,"
            " such as mona-cat_octo; for <name>, use letters, digits, '.', '-' and '_',"
            " other than . and .., such as nustack"
        )

    def test_reads_the_owner_and_the_name(self) -> None:
        assert NameWithOwner.parse("o/r") == NameWithOwner("o", "r")

    @pytest.mark.parametrize(
        ("value", "what"),
        [
            (
                "o",
                "give the repository as <owner>/<name>, not o",
            ),
            (
                "o/",
                "give the repository as <owner>/<name>, not o/",
            ),
            (
                "/r",
                "give the repository as <owner>/<name>, not /r",
            ),
            (
                "o/r/x",
                "give the repository as <owner>/<name>, not o/r/x",
            ),
        ],
    )
    def test_refuses_a_value_of_another_form(self, value: str, what: str) -> None:
        with pytest.raises(GitHubNameError) as caught:
            NameWithOwner.parse(value)
        assert str(caught.value) == what

    @pytest.mark.parametrize(
        ("value", "what"),
        [
            (
                "../x",
                (
                    "give the repository as GitHub names it, not ../x; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "o/..",
                (
                    "give the repository as GitHub names it, not o/..; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "o/.",
                (
                    "give the repository as GitHub names it, not o/.; for <owner>, use "
                    "letters, digits and single hyphens, with no hyphen first or last, "
                    "such as Nusnus, and for a managed user an underscore and its "
                    "enterprise's short code at the end, such as mona-cat_octo; for "
                    "<name>, use letters, digits, '.', '-' and '_', other than . and "
                    ".., such as nustack"
                ),
            ),
            (
                "a b/c",
                (
                    "give the repository as GitHub names it, not a b/c; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "-o/n",
                (
                    "give the repository as GitHub names it, not -o/n; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "o-/n",
                (
                    "give the repository as GitHub names it, not o-/n; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "o--p/n",
                (
                    "give the repository as GitHub names it, not o--p/n; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "o/n?x",
                (
                    "give the repository as GitHub names it, not o/n?x; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "o_/n",
                (
                    "give the repository as GitHub names it, not o_/n; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "_o/n",
                (
                    "give the repository as GitHub names it, not _o/n; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "a_b_c/n",
                (
                    "give the repository as GitHub names it, not a_b_c/n; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
            (
                "o-_x/n",
                (
                    "give the repository as GitHub names it, not o-_x/n; for <owner>, "
                    "use letters, digits and single hyphens, with no hyphen first or "
                    "last, such as Nusnus, and for a managed user an underscore and "
                    "its enterprise's short code at the end, such as mona-cat_octo; "
                    "for <name>, use letters, digits, '.', '-' and '_', other than . "
                    "and .., such as nustack"
                ),
            ),
        ],
    )
    def test_refuses_an_owner_or_name_github_would_not_take(
        self, value: str, what: str
    ) -> None:
        with pytest.raises(GitHubNameError) as caught:
            NameWithOwner.parse(value)
        assert str(caught.value) == what

    @pytest.mark.parametrize(
        ("value", "read"),
        [
            ("Nus-1/a.b_c-D", NameWithOwner("Nus-1", "a.b_c-D")),
            ("o/.github", NameWithOwner("o", ".github")),
            ("mona-cat_octo/r", NameWithOwner("mona-cat_octo", "r")),
            ("o/...", NameWithOwner("o", "...")),
        ],
    )
    def test_reads_an_owner_and_name_github_takes(
        self, value: str, read: NameWithOwner
    ) -> None:
        assert NameWithOwner.parse(value) == read

    def test_reads_as_owner_slash_name(self) -> None:
        assert str(NameWithOwner("o", "r")) == "o/r"


class TestRepositoryUrl:
    """An https URL of <owner>/<name> on a host reads as both; any other URL fails.

    The host keeps the case it is written in, and holds no user, password or port. A
    URL fails without repeating it, and so does one whose owner or name GitHub would
    not take, or one that reads back other than as written. It reads back as
    https://<host>/<owner>/<name>. One built from a host that is not a host name
    fails too.
    """

    @pytest.mark.parametrize(
        "host",
        [
            "",
            "t@github.com",
            "github.com:443",
            "a/b",
            "ex ample.com",
            "exa%6dple.com",
            "-github.com",
            "github-.com",
            "github..com",
            "github.com.",
        ],
    )
    def test_refuses_to_build_from_a_host_that_is_not_a_host_name(
        self, host: str
    ) -> None:
        with pytest.raises(GitHubNameError) as caught:
            RepositoryUrl(host, NameWithOwner("o", "r"))
        assert str(caught.value) == (
            "give the host as a host name; use labels of letters, digits and hyphens,"
            " joined by dots, with no hyphen first or last in a label, such as"
            " github.com"
        )

    @pytest.mark.parametrize(
        ("host", "url"),
        [
            ("github.com", "https://github.com/o/r"),
            ("a-b.c0", "https://a-b.c0/o/r"),
            ("x--y.example.org", "https://x--y.example.org/o/r"),
        ],
    )
    def test_builds_from_a_host_name(self, host: str, url: str) -> None:
        assert str(RepositoryUrl(host, NameWithOwner("o", "r"))) == url

    def test_reads_the_host_and_the_name(self) -> None:
        assert RepositoryUrl.parse("https://github.com/o/r") == RepositoryUrl(
            "github.com", NameWithOwner("o", "r")
        )

    def test_keeps_the_host_as_written(self) -> None:
        assert RepositoryUrl.parse("https://GitHub.com/o/r") == RepositoryUrl(
            "GitHub.com", NameWithOwner("o", "r")
        )

    @pytest.mark.parametrize(
        "value",
        [
            "http://github.com/o/r",
            "https:///o/r",
            "https://github.com:99999/o/r",
            "https://github.com:/o/r",
            "https://github.com/o",
            "https://github.com//r",
            "https://github.com/o/",
            "https://github.com/o/r/x",
            "https://github.com/o/r?tab=readme",
            "https://github.com/o/r#readme",
            "https://user:SECRET@github.com/o/r",
            "https://x-access-token:SECRET@github.com/o/n",
            "https://SECRET@github.com/o/n",
            "https://github.com/o/r?access_token=SECRET",
            "https:/SECRET@github.com/o/r",
            "https://ex ample.com/o/r",
            "https://exa%6dple.com/o/r",
            "https://ex\nample.com/o/r",
            "https://github.com/o/r\t",
            "https://github.com/o/r?",
            "https://github.com/o/r#",
        ],
    )
    def test_refuses_a_url_of_another_form_without_repeating_it(
        self, value: str
    ) -> None:
        with pytest.raises(GitHubNameError) as caught:
            RepositoryUrl.parse(value)
        assert str(caught.value) == (
            "give the repository's URL as https://<host>/<owner>/<name>, with no user,"
            " password, port, query or fragment"
        )

    @pytest.mark.parametrize(
        "value", ["https://github.com/../SECRET", "https://github.com/SECRET_/r"]
    )
    def test_refuses_an_owner_or_name_github_would_not_take_without_repeating_it(
        self, value: str
    ) -> None:
        with pytest.raises(GitHubNameError) as caught:
            RepositoryUrl.parse(value)
        assert str(caught.value) == (
            "give the repository's URL with an owner and name GitHub would take; for"
            " <owner>, use letters, digits and single hyphens, with no hyphen first or"
            " last, such as Nusnus, and for a managed user an underscore and its"
            " enterprise's short code at the end, such as mona-cat_octo; for <name>,"
            " use letters, digits, '.', '-' and '_', other than . and .., such as"
            " nustack"
        )

    def test_reads_as_an_https_url(self) -> None:
        assert str(RepositoryUrl("x.io", NameWithOwner("o", "r"))) == "https://x.io/o/r"

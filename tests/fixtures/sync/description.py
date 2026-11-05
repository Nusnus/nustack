"""The passages the sync's description repeats, shared by the tests that read it."""

from enum import StrEnum


class Passage(StrEnum):
    """A passage the sync's description repeats, in the order it prints them."""

    CI = (
        "\n- [CI](https://checks): pending. Approve this pull request's workflows if"
        " prompted; the linked runs hold the results."
    )
    UNKNOWN_COMMIT = (
        "The base's record names no commit that upstream's head holds, so the commit"
        " range is unknown"
    )
    TERMS = (
        "Terms and loading:\n\n- LICENSE: unchanged\n- SKILL.md frontmatter: unchanged"
        "\n- agents/ policy files: unchanged\n\n"
    )
    NO_COMMITS = (
        "Upstream commits touching the skills or repository LICENSE (0): none.\n\n"
    )
    EMPTY_SCANS = (
        "\n\nNew upstream skills the record does not list (0): none."
        "\n\nNew outside CommonMark targets by file (0): none."
        "\n\nLines to inspect (0; - base, + copy): none."
    )
    NOTES = (
        "\n\nHow the scans read:\n\n- Links: net new destinations per file that the"
        " CommonMark parser recognizes as links or images; check raw HTML, bare URLs"
        " and email addresses, and rejected URI schemes in the diff\n- Lines: edits"
        " in SKILL.md frontmatter and agents/, plus added lines naming rules,"
        " invocation fields, selected commands or HTTP(S) URLs\n- Both scans skip"
        " binary comparisons"
    )

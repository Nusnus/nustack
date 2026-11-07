"""The passages the sync's description repeats, shared by the tests that read it."""

from enum import StrEnum


class Passage(StrEnum):
    """A passage the sync's description repeats, in the order it prints them."""

    CI = (
        "\n- [CI](https://checks): pending. Approve this pull request's workflows if"
        " prompted; the linked runs hold the results."
    )
    TERMS = (
        "##### Terms and loading\n\n- LICENSE: unchanged\n- SKILL.md frontmatter:"
        " unchanged\n- agents/ policy files: unchanged\n\n"
    )
    UNKNOWN_COMMITS = (
        "##### Upstream commits touching the skills or repository LICENSE\n\n"
        "- Unknown: the base's record names no commit upstream's head holds\n\n"
    )
    RECORD = (
        "\n\n##### The copy's record (1)\n\n- ` vendored/copy.json `: its commit and"
        " blobs, rewritten to upstream's"
    )
    EMPTY_SCANS = (
        "\n\n##### New upstream skills the record does not list (0)\n\nNone."
        "\n\n##### New outside CommonMark targets by file (0)\n\nNone."
        "\n\n##### Lines to inspect (0; - base, + copy)\n\nNone."
    )
    NOTES = (
        "\n\n##### How the scans read\n\n- Links: net new link and image targets per"
        " file, as CommonMark parses them\n- Links miss raw HTML, bare URLs, email"
        " addresses and rejected URI schemes, which only the diff shows\n- Lines:"
        " every edit in SKILL.md frontmatter and agents/\n- Lines: added lines naming"
        " rules, invocation fields, selected commands or HTTP(S) URLs\n- Both scans"
        " skip binary comparisons"
    )

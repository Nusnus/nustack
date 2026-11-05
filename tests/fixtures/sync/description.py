"""The passages the sync's description repeats, shared by the tests that read it."""

from enum import StrEnum


class Passage(StrEnum):
    """A passage the sync's description repeats, in the order it prints them."""

    CI = (
        "\n| ⚠️ **[CI](https://checks)** | Approve this pull request's workflows if"
        " prompted; see the linked runs for results. |"
    )
    UNKNOWN_COMMIT = (
        "The base's record names no commit that upstream's head holds. The commit"
        " range is unknown."
    )
    EMPTY_SCANS = (
        "\n\n**New upstream skills the record does not list (0).**"
        "\n\n**New outside CommonMark targets by file (0).**"
        "\n\n**Lines to inspect (0; - base, + copy).**"
    )
    NOTES = (
        "\n\n**Links:** net new destinations per file that the CommonMark parser"
        " recognizes as links or images. Check raw HTML, bare URLs and email"
        " addresses, and rejected URI schemes in the diff.\n\n**Lines:** edits in"
        " `SKILL.md` frontmatter and `agents/`, plus added lines naming rules,"
        " invocation fields, selected commands or HTTP(S) URLs. Both scans skip"
        " binary comparisons.\n\n**Owner"
        " review:** read the whole diff for instructions beyond wording, claims of"
        " authority or wider loading. These cues cannot decide any of them."
    )

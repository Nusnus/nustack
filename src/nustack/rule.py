"""The structural rules `nustack check` enforces, as its help lists them."""

from enum import StrEnum


class Rule(StrEnum):
    """One structural rule `nustack check` enforces."""

    METADATA = (
        "the manifests, both marketplaces, plugin/package.json and pyproject.toml "
        "agree on the plugin's name, version, description and author, and the "
        "marketplaces on their own name and description"
    )
    PLUGIN_FILES = (
        "plugin/ holds only the host manifests, skills, playbooks, the OpenCode "
        "loader with its package.json, the Claude Code hook that reloads the mode, "
        "and a LICENSE equal to the repository's"
    )
    SAFE_TO_READ = (
        "plugin/ is a folder that holds no symlink and no folder the check cannot "
        "open, and a break of either stops the check before it reads anything else"
    )
    SKILLS = (
        "each skill folder names the mode or starts with a skill prefix spelled "
        "right, its frontmatter and triggers follow Writing skill text, and its "
        "SKILL.md stays under the line limit"
    )
    MODE = (
        "plugin/skills/ holds exactly one mode, every plugin document calls it by "
        "its name, its body opens with its title and fits the Claude Code hook's "
        "output, and it indexes each playbook, principle and language skill under "
        "its own heading"
    )
    PLAYBOOK_STEPS = "each playbook step ends on a done condition"
    SKILL_TEXT = "skill text names no agent host, model, host's folder or date"
    LINKS = (
        "every link in plugin/ is a full URL or a relative path to a file there, "
        "and each anchor names a heading in that file"
    )
    CHANGELOG = (
        "CHANGELOG.md titles, dates and orders every release, opens with the plugin "
        "version's entry, which resolves each reference label it uses the same on its "
        "own, in the changelog and on the release page, gives each link and image a "
        "full URL and groups its changes under Keep a Changelog's types, in their "
        "order, each type once and each group showing something, and links each "
        "release to its tag and [Unreleased] to the changes since the plugin version"
    )
    VENDORED = (
        "the commit hooks that rewrite text, and Ruff's extend-exclude, skip the "
        "folder the writing-for-agents sync copies into"
    )
    ACTIVATION = "README.md's activation line is the new-project playbook's"
    PAGE_STEPS = (
        "README.md holds one ### 1️⃣ Install and one ### 2️⃣ Use section for the "
        "release page, each of which shows something, gives each link and image a "
        "full URL and resolves each reference label it uses the same on its own, in "
        "README.md and on the release page"
    )
    TEST_LAYOUT = (
        "each test module sits in a tier folder and mirrors the path of the source "
        "it tests, apart from smoke tests and the tests of the suite's own settings, "
        "and a tier folder holds no file but tests and conftest.py"
    )

    @classmethod
    def help(cls) -> str:
        return (
            "Hold the repository to these rules:\n\n"
            + ";\n".join(f"- {rule}" for rule in cls)
            + "."
        )

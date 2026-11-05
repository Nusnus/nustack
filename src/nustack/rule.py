"""The structural rules `nustack check` enforces, as its help lists them."""

from enum import StrEnum


class Rule(StrEnum):
    """One structural rule `nustack check` enforces."""

    METADATA = (
        "the host manifests agree in every field, plugin/package.json holds their "
        "name and version, and pyproject.toml their version; each marketplace "
        "lists only the plugin, with the manifests' name and description and its "
        "host's source, and names the manifests' author as its owner; and both "
        "marketplaces have one name and one description"
    )
    VERSION_FILES = (
        "commitizen's version_files in pyproject.toml lists, once each, every other "
        "file whose version the check compares"
    )
    RELEASE_TAG = (
        "commitizen's tag_format in pyproject.toml, and the release workflow's push "
        "tags filter, each name the tag form nustack release-tag takes"
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
        "SKILL.md stays under the line limit; a vendored skill, which a record in "
        "vendored/ names, needs only a name matching its folder and a description"
    )
    MODE = (
        "plugin/skills/ holds exactly one mode, every plugin document outside the "
        "vendored skills calls it by its name, its body opens with its title and "
        "fits the Claude Code hook's output, and it indexes each playbook, "
        "principle and language skill under its own heading"
    )
    PLAYBOOK_STEPS = "each playbook step ends on a done condition"
    SKILL_TEXT = (
        "skill text outside the vendored skills names no agent host, model, host's "
        "folder or date"
    )
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
        "vendored/ holds only records named <copy>.json, with <copy> in kebab case; "
        "each is valid, names skill "
        "folders no other record names, holds or sits in, copies no skill named as "
        "the mode, a principle or a language skill, copies nothing from this "
        "repository, and copies only into .agents/skills or plugin/skills; each "
        "folder it names holds exactly the files it lists, with the bytes it lists; "
        "a skill folder there that holds a LICENSE has a record; and the commit "
        "hooks that rewrite text, and Ruff's extend-exclude, skip exactly the "
        "folders the records name, and .gitattributes ends on a line that unsets "
        "text for each of them"
    )
    ACTIVATION = "README.md's activation line is the new-project playbook's"
    SKILL_TABLE = (
        "README.md's tables headed 'Skill' and 'What it holds' give each principle and "
        "language skill a row that links its SKILL.md under the skill's name and "
        "holds the description its SKILL.md holds, give each vendored skill a row "
        "that links its SKILL.md under the skill's name, and every row links a "
        "skill's SKILL.md, no skill's twice"
    )
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

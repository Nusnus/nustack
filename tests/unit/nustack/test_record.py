"""A record names one vendored copy's upstream, skills, commit and file blobs.

A record that breaks its schema, or lists files that no sync could have copied, is
invalid with a reason naming the field and the fix.
"""

import json
import re
from pathlib import Path
from pathlib import PurePosixPath

import pytest
from pydantic import ValidationError

from nustack.problem import Problem
from nustack.record import CopyRecord
from nustack.record import InvalidRecordError
from nustack.sha import Sha
from nustack.tree import File


class TestCopyRecord:
    """Each file sits under a listed skill, beside that skill's SKILL.md and LICENSE.

    A record before its first sync names no commit and no files. Its text is stable
    JSON, and a blob is named as Git names it.
    """

    FIELDS = frozendict(
        {
            "upstream": "https://github.com/up/skills",
            "source": "skills",
            "folder": "plugin/skills",
            "skills": ["a", "b"],
            "commit": "c" * 40,
            "files": {
                "a/LICENSE": "1" * 40,
                "a/SKILL.md": "2" * 40,
                "b/LICENSE": "1" * 40,
                "b/SKILL.md": "3" * 40,
                "b/references/R.md": "4" * 40,
            },
        }
    )
    URL_FORM = (
        "upstream: give the repository's URL as https://<host>/<owner>/<name>, with"
        " no user, password, port, query or fragment"
    )
    URL_GIT = "upstream: write the URL with no .git suffix"
    URL_NAMES = (
        "upstream: give the repository's URL with an owner and name GitHub would"
        " take; for <owner>, use letters, digits and single hyphens, with no hyphen"
        " first or last, such as Nusnus, and for a managed user an underscore and its"
        " enterprise's short code at the end, such as mona-cat_octo; for <name>, use"
        " letters, digits, '.', '-' and '_', other than . and .., such as nustack"
    )

    @pytest.mark.parametrize(
        ("fields", "message"),
        [
            (
                {"source": "skills/"},
                (
                    "source: write a relative path with no . or .. part, no //,"
                    " and no / at either end"
                ),
            ),
            (
                {"source": "."},
                (
                    "source: write a relative path with no . or .. part, no //,"
                    " and no / at either end"
                ),
            ),
            (
                {"source": "/skills"},
                (
                    "source: write a relative path with no . or .. part, no //,"
                    " and no / at either end"
                ),
            ),
            (
                {"source": ""},
                (
                    "source: write a relative path with no . or .. part, no //,"
                    " and no / at either end"
                ),
            ),
            (
                {"source": "skills/./a"},
                (
                    "source: write a relative path with no . or .. part, no //,"
                    " and no / at either end"
                ),
            ),
            (
                {"folder": "../plugin"},
                (
                    "folder: write a relative path with no . or .. part, no //,"
                    " and no / at either end"
                ),
            ),
            (
                {"folder": "plugin/../skills"},
                (
                    "folder: write a relative path with no . or .. part, no //,"
                    " and no / at either end"
                ),
            ),
            (
                {"folder": "plugin//skills"},
                (
                    "folder: write a relative path with no . or .. part, no //,"
                    " and no / at either end"
                ),
            ),
            (
                {"files": {"a/../LICENSE": "1" * 40}},
                (
                    "files: for each key, write a relative path with no . or .. part,"
                    " no //, and no / at either end"
                ),
            ),
            (
                {"files": {"a/\x1b[31m.md": "1" * 40}},
                (
                    "files: for each key, write each part of the path in letters,"
                    " digits, ., _ and - alone"
                ),
            ),
            (
                {"files": {"a/b c.md": "1" * 40}},
                (
                    "files: for each key, write each part of the path in letters,"
                    " digits, ., _ and - alone"
                ),
            ),
            (
                {"files": {"a/x\n fake: line": "1" * 40}},
                (
                    "files: for each key, write each part of the path in letters,"
                    " digits, ., _ and - alone"
                ),
            ),
            (
                {"files": {"a/é.md": "1" * 40}},
                (
                    "files: for each key, write each part of the path in letters,"
                    " digits, ., _ and - alone"
                ),
            ),
        ],
    )
    def test_reports_a_path_that_is_not_plain(
        self, fields: dict[str, object], message: str
    ) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(json.dumps(dict(self.FIELDS) | fields).encode())
        assert str(invalid.value) == message

    def test_takes_file_paths_of_letters_digits_dots_underscores_and_dashes(
        self,
    ) -> None:
        files = {
            "a/LICENSE": "1" * 40,
            "a/SKILL.md": "2" * 40,
            "a/.ref/A_b-1.2.md": "3" * 40,
            "b/LICENSE": "1" * 40,
            "b/SKILL.md": "4" * 40,
        }
        record = CopyRecord.parse(
            json.dumps(dict(self.FIELDS) | {"files": files}).encode()
        )
        assert dict(record.files) == files

    @pytest.mark.parametrize(
        ("upstream", "fix"),
        [
            (
                "https://github.com/up/skills.git",
                URL_GIT,
            ),
            (
                "git@github.com:up/skills",
                URL_FORM,
            ),
            (
                "http://github.com/up/skills",
                URL_FORM,
            ),
            (
                "https:///up/skills",
                URL_FORM,
            ),
            (
                "https://github.com/up/skills?tab=readme",
                URL_FORM,
            ),
            (
                "https://github.com/up/skills#readme",
                URL_FORM,
            ),
            (
                "https://github.com/up",
                URL_FORM,
            ),
            (
                "https://github.com/up/",
                URL_FORM,
            ),
            (
                "https://user:secret@github.com/up/skills",
                URL_FORM,
            ),
            (
                "https://user@github.com/up/skills",
                URL_FORM,
            ),
            (
                "https://github.com:443/up/skills",
                URL_FORM,
            ),
            (
                "HTTPS://github.com/up/skills",
                URL_FORM,
            ),
            (
                "https://github.com/up/skills?",
                URL_FORM,
            ),
            (
                "https://github.com/up/skills#",
                URL_FORM,
            ),
            (
                "https://github.com/up/ski lls",
                URL_NAMES,
            ),
            (
                "https://github.com/up/skills\n",
                URL_FORM,
            ),
            (
                "https://github.com/up/skïlls",
                URL_NAMES,
            ),
            (
                "https://github.com/../..",
                URL_NAMES,
            ),
            (
                "https://github.com/up/.",
                URL_NAMES,
            ),
            (
                "https://github.com/_up/-s.",
                URL_NAMES,
            ),
        ],
    )
    def test_reports_an_upstream_that_is_no_repositorys_https_url(
        self, upstream: str, fix: str
    ) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(
                json.dumps(dict(self.FIELDS) | {"upstream": upstream}).encode()
            )
        assert str(invalid.value) == fix

    @pytest.mark.parametrize(
        "upstream",
        [
            "https://github.com/up/skills",
            "https://github.com/Up_1/s.k-2",
            "https://github.com/up-1/-s.",
            "https://github.com/up/.skills",
            "https://github.com/github/.github",
            "https://GitHub.com/up/skills",
        ],
    )
    def test_takes_an_upstream_whose_owner_and_name_github_takes(
        self, upstream: str
    ) -> None:
        record = CopyRecord.parse(
            json.dumps(dict(self.FIELDS) | {"upstream": upstream}).encode()
        )
        assert str(record.upstream) == upstream

    def test_names_each_skills_folder_upstream_and_here(self) -> None:
        record = CopyRecord.parse(json.dumps(dict(self.FIELDS)).encode())
        assert (
            record.upstream_folders,
            [str(folder) for folder in record.skill_folders],
            dict(record.files_of("b")),
        ) == (
            ("skills/a", "skills/b"),
            ["plugin/skills/a", "plugin/skills/b"],
            {"LICENSE": "1" * 40, "SKILL.md": "3" * 40, "references/R.md": "4" * 40},
        )

    def test_takes_a_record_before_its_first_sync(self) -> None:
        record = CopyRecord.parse(
            json.dumps(dict(self.FIELDS) | {"commit": None, "files": {}}).encode()
        )
        assert (record.commit, dict(record.files)) == (None, {})

    def test_names_an_authored_skill_before_the_files_it_lacks(self) -> None:
        skills = {"skills": ["a", "b", "principle-dry"]}
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(json.dumps(dict(self.FIELDS) | skills).encode())
        assert str(invalid.value) == (
            "skills: lists a skill whose name starts with principle- or language- or"
            " ends in -mode, which only nustack's authors write; drop it from skills"
        )

    @pytest.mark.parametrize(
        ("fields", "message"),
        [
            ({"skills": []}, "skills: list each skill the copy holds, once"),
            (
                {"skills": ["a" * 65]},
                "skills.0: shorten it to at most 64 characters",
            ),
            (
                {"skills": ["a", "b", "a"]},
                "skills: list each skill the copy holds, once",
            ),
            (
                {"commit": None},
                (
                    "commit and files: set both from one sync, or set commit"
                    " to null and files to {} until the first sync"
                ),
            ),
            (
                {"files": {}},
                (
                    "commit and files: set both from one sync, or set commit"
                    " to null and files to {} until the first sync"
                ),
            ),
            (
                {"skills": ["a"]},
                "files: put each file under a skill the record lists",
            ),
            (
                {
                    "files": {
                        "a": "1" * 40,
                        "a/LICENSE": "1" * 40,
                        "a/SKILL.md": "2" * 40,
                    }
                },
                "files: put each file under a skill the record lists",
            ),
            (
                {"files": {"a/SKILL.md": "2" * 40, "b/SKILL.md": "3" * 40}},
                "files: give each skill its SKILL.md and LICENSE",
            ),
        ],
    )
    def test_reports_files_no_sync_could_have_copied(
        self, fields: dict[str, object], message: str
    ) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(json.dumps(dict(self.FIELDS) | fields).encode())
        assert str(invalid.value) == message

    @pytest.mark.parametrize(
        ("fields", "reason"),
        [
            ({"upstream": 1}, "upstream: make it a string"),
            ({"commit": 1}, "commit: make it a string"),
            ({"skills": ["A"]}, "skills.0: use kebab case, such as nus-mode"),
            ({"folder": 1}, "folder: make it a string"),
            (
                {"commit": "c" * 7},
                (
                    "commit: use 40 lowercase hex digits, such as"
                    " 81c986c0e0a7c511f2941ed3cec09f7975687f80"
                ),
            ),
        ],
    )
    def test_reports_a_field_that_breaks_the_schema(
        self, fields: dict[str, object], reason: str
    ) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(json.dumps(dict(self.FIELDS) | fields).encode())
        assert str(invalid.value) == reason

    def test_reports_a_files_value_that_is_no_object_name(self) -> None:
        files = {"a/LICENSE": "1" * 40, "a/SKILL.md": "XYZ"}
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(
                json.dumps(dict(self.FIELDS) | {"files": files}).encode()
            )
        assert str(invalid.value) == (
            "files.<key>: use 40 lowercase hex digits, such as"
            " 81c986c0e0a7c511f2941ed3cec09f7975687f80"
        )

    def test_reports_a_key_written_twice(self) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(
                json.dumps(dict(self.FIELDS))
                .encode()
                .replace(
                    b'"source": "skills"', b'"source": "skills", "source": "other"'
                )
            )
        assert str(invalid.value) == (
            "has the key 'source' more than once in the file; keep one"
        )

    def test_reports_a_key_written_twice_beside_a_field_that_breaks_the_schema(
        self,
    ) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(
                json.dumps(dict(self.FIELDS) | {"commit": "c"})
                .encode()
                .replace(
                    b'"source": "skills"', b'"source": "skills", "source": "other"'
                )
            )
        assert str(invalid.value) == (
            "has the key 'source' more than once in the file; keep one; commit: use"
            " 40 lowercase hex digits, such as 81c986c0e0a7c511f2941ed3cec09f7975687f80"
        )

    @pytest.mark.parametrize("files", [[], "a/SKILL.md", None])
    def test_reports_files_that_are_no_object(self, files: object) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(
                json.dumps(dict(self.FIELDS) | {"files": files}).encode()
            )
        assert str(invalid.value) == "files: make it an object of keys and values"

    def test_reports_an_unknown_key(self) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(
                json.dumps(dict(self.FIELDS) | {"extra": True}).encode()
            )
        assert str(invalid.value) == (
            "an unknown key: rename it or remove it; nustack allows only upstream,"
            " source, folder, skills, commit, files here"
        )

    def test_reports_text_that_is_no_json(self) -> None:
        with pytest.raises(InvalidRecordError) as invalid:
            _ = CopyRecord.parse(b"{")
        assert str(invalid.value) == (
            "the file: fix the JSON (EOF while parsing an object at line 1 column 1)"
        )

    @pytest.mark.parametrize(
        "content",
        [
            json.dumps(dict(FIELDS), indent=4) + "\n",
            json.dumps(dict(FIELDS), indent=2),
            json.dumps(
                dict(FIELDS)
                | {
                    "files": {
                        "b/references/R.md": "4" * 40,
                        "b/SKILL.md": "3" * 40,
                        "b/LICENSE": "1" * 40,
                        "a/SKILL.md": "2" * 40,
                        "a/LICENSE": "1" * 40,
                    }
                },
                indent=2,
            )
            + "\n",
            json.dumps(
                dict(FIELDS) | {"source": "skills/é"}, indent=2, ensure_ascii=False
            )
            + "\n",
        ],
    )
    def test_reports_a_record_laid_out_other_than_the_sync_writes_it(
        self, content: str
    ) -> None:
        assert CopyRecord.reading(
            Path("/"), PurePosixPath("vendored/r.json"), File(content.encode()), ""
        ) == Problem(
            Path("/vendored/r.json"),
            "is laid out other than the sync writes it; write it as JSON indented by"
            " 2 spaces, with its keys in the order upstream, source, folder, skills,"
            " commit, files, its files sorted, every non-ASCII character escaped as"
            " \\uXXXX and one newline at the end",
        )

    def test_reports_a_record_that_is_not_utf_8(self) -> None:
        assert CopyRecord.reading(
            Path("/"),
            PurePosixPath("vendored/r.json"),
            File(b'{"upstream": "\xff"}\n'),
            "",
        ) == Problem(Path("/vendored/r.json"), "is not valid UTF-8; save it as UTF-8")

    @pytest.mark.parametrize(
        ("path", "where", "what"),
        [
            (
                "r.json",
                Path("/r.json"),
                (
                    "is no record the sync reads; name it vendored/<copy>.json, with"
                    " <copy> in kebab case such as obsidian-skills"
                ),
            ),
            (
                "vendored/sub/r.json",
                Path("/vendored/sub/r.json"),
                (
                    "is no record the sync reads; name it vendored/<copy>.json, with"
                    " <copy> in kebab case such as obsidian-skills, or move it out of"
                    " vendored/"
                ),
            ),
            (
                "vendored/r.JSON",
                Path("/vendored/r.JSON"),
                (
                    "is no record the sync reads; name it vendored/<copy>.json, with"
                    " <copy> in kebab case such as obsidian-skills, or move it out of"
                    " vendored/"
                ),
            ),
            (
                "vendored/.hidden.json",
                Path("/vendored/.hidden.json"),
                (
                    "is no record the sync reads; name it vendored/<copy>.json, with"
                    " <copy> in kebab case such as obsidian-skills, or move it out of"
                    " vendored/"
                ),
            ),
            (
                "vendored/Foo Bar.json",
                Path("/vendored/Foo Bar.json"),
                (
                    "is no record the sync reads; name it vendored/<copy>.json, with"
                    " <copy> in kebab case such as obsidian-skills, or move it out of"
                    " vendored/"
                ),
            ),
            (
                "vendored/r_s.json",
                Path("/vendored/r_s.json"),
                (
                    "is no record the sync reads; name it vendored/<copy>.json, with"
                    " <copy> in kebab case such as obsidian-skills, or move it out of"
                    " vendored/"
                ),
            ),
        ],
    )
    def test_reports_a_record_the_sync_never_reads(
        self, path: str, where: Path, what: str
    ) -> None:
        content = json.dumps(dict(self.FIELDS), indent=2) + "\n"
        assert CopyRecord.reading(
            Path("/"), PurePosixPath(path), File(content.encode()), ""
        ) == Problem(where, what)

    def test_reads_a_record_laid_out_as_the_sync_writes_it(self) -> None:
        content = json.dumps(dict(self.FIELDS), indent=2) + "\n"
        record = CopyRecord.reading(
            Path("/"),
            PurePosixPath("vendored/obsidian-skills.json"),
            File(content.encode()),
            "",
        )
        assert isinstance(record, CopyRecord)
        assert record.model_dump(mode="json") == dict(self.FIELDS)

    def test_names_a_blob_as_git_does(self) -> None:
        assert (CopyRecord.blob(b""), CopyRecord.blob(b"MIT\n")) == (
            "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
            "a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc",
        )

    def test_writes_a_copy_as_sorted_json_that_reads_back_the_same(self) -> None:
        record = CopyRecord.parse(
            json.dumps(dict(self.FIELDS) | {"commit": None, "files": {}}).encode()
        ).copied(
            Sha("d" * 40),
            frozendict(
                {
                    "b/SKILL.md": "3" * 40,
                    "a/SKILL.md": "2" * 40,
                    "a/LICENSE": "1" * 40,
                    "b/LICENSE": "1" * 40,
                }
            ),
        )
        assert (record.text, CopyRecord.parse(record.text.encode())) == (
            (
                "{\n"
                '  "upstream": "https://github.com/up/skills",\n'
                '  "source": "skills",\n'
                '  "folder": "plugin/skills",\n'
                '  "skills": [\n'
                '    "a",\n'
                '    "b"\n'
                "  ],\n"
                f'  "commit": "{"d" * 40}",\n'
                '  "files": {\n'
                f'    "a/LICENSE": "{"1" * 40}",\n'
                f'    "a/SKILL.md": "{"2" * 40}",\n'
                f'    "b/LICENSE": "{"1" * 40}",\n'
                f'    "b/SKILL.md": "{"3" * 40}"\n'
                "  }\n"
                "}\n"
            ),
            record,
        )

    def test_refuses_a_copy_whose_files_break_the_record(self) -> None:
        record = CopyRecord.parse(
            json.dumps(dict(self.FIELDS) | {"commit": None, "files": {}}).encode()
        )
        with pytest.raises(
            ValidationError,
            match=re.escape("files: give each skill its SKILL.md and LICENSE"),
        ):
            _ = record.copied(Sha("d" * 40), frozendict({"a/SKILL.md": "2" * 40}))

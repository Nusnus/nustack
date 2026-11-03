"""The parts of a file the release page copies, each checked to read the same there.

The page copies the changelog entry and README's install and use steps outside the
repository, where a relative link breaks and a reference defined elsewhere in the
file reads as text. So each part shows something, gives each link and image a full
URL and defines the references it uses, and once the page joins the parts, none uses
a label another part defines differently. README holds exactly one section for each
page step, PageStep, which the page copies.
"""

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

from nustack.problem import Problem
lazy from nustack.markdown.document import Definitions
lazy from nustack.markdown.document import Document
lazy from nustack.markdown.document import Section


@dataclass(frozen=True)
class PagePart:
    """A section the release page copies.

    It holds how a problem names the section and the fix when the section shows
    nothing.
    """

    document: Document
    section: Section
    name: str
    nothing_shown_fix: str

    @cached_property
    def shows(self) -> bool:
        return self.document.shows(self.section.body)

    @property
    def problems(self) -> list[Problem]:
        path, body = self.document.path, self.section.body
        problems: list[Problem] = []
        if not self.shows:
            problems.append(
                Problem(
                    path,
                    f"shows nothing in {self.name}; {self.nothing_shown_fix}",
                )
            )
        if not self.document.stands_alone(body):
            problems.append(
                Problem(
                    path,
                    f"uses a reference in {self.name} that is defined elsewhere in"
                    " the file, so it reads differently on the release page; define"
                    f" it inside {self.name}, under a label no other definition in the"
                    " file uses",
                )
            )
        problems += [
            Problem(
                path,
                f"links {href} from {self.name}, which the release page copies,"
                " where a relative link breaks; link it by its full URL",
            )
            for href in dict.fromkeys(self.document.relative_hrefs(self.section))
        ]
        return problems

    def page_problems(self, definitions: Definitions) -> list[Problem]:
        if Document.stands_alone_beside(self.section.body, definitions):
            return []
        return [
            Problem(
                self.document.path,
                f"uses a reference label in {self.name} that another part of the"
                " release page defines, so it reads differently on the page, which"
                f" joins them; define the reference inside {self.name}, under a label"
                " no other part of the page defines",
            )
        ]


class PageStep(StrEnum):
    """One of README's install and use steps, a section the release page copies."""

    INSTALL = "1️⃣ Install"
    USE = "2️⃣ Use"

    @property
    def heading(self) -> str:
        return f"### {self}"

    def problems(self, readme: Document, parts: tuple[PagePart, ...]) -> list[Problem]:
        if not parts:
            return [
                Problem(
                    readme.path,
                    f"has no '{self.heading}' section, which the release page"
                    " copies; add one",
                )
            ]
        problems = [problem for part in parts for problem in part.problems]
        if len(parts) > 1:
            problems.append(
                Problem(
                    readme.path,
                    f"has {len(parts)} '{self.heading}' sections, where the"
                    " release page copies one; merge them into one",
                )
            )
        return problems

    def part(
        self, readme: Document, section: Section, number: int, count: int
    ) -> PagePart:
        position = f" {number} of {count}" if count > 1 else ""
        return PagePart(
            readme,
            section,
            f"its '{self.heading}' section{position}",
            "write the steps the release page copies from it"
            if number == 1
            else "remove it, since the release page copies one",
        )


@dataclass(frozen=True)
class PageSteps:
    """README's sections for each page step, which the release page copies once each.

    The page joins the sections once each step has exactly one, even while one of
    them breaks another rule, so every rule reports at once.
    """

    readme: Document

    @cached_property
    def found(self) -> frozendict[PageStep, tuple[Section, ...]]:
        headed = self.readme.headed(3)
        return frozendict(
            (step, tuple(each for each in headed if each.title == step))
            for step in PageStep
        )

    @cached_property
    def parts(self) -> frozendict[PageStep, tuple[PagePart, ...]]:
        return frozendict(
            (
                step,
                tuple(
                    step.part(self.readme, section, number, len(sections))
                    for number, section in enumerate(sections, 1)
                ),
            )
            for step, sections in self.found.items()
        )

    @cached_property
    def sections(self) -> frozendict[PageStep, Section] | None:
        if any(len(sections) != 1 for sections in self.found.values()):
            return None
        return frozendict((step, section) for step, (section,) in self.found.items())

    @property
    def problems(self) -> list[Problem]:
        return [
            problem
            for step, parts in self.parts.items()
            for problem in step.problems(self.readme, parts)
        ]

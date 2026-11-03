"""The page-step rule's text, held to the steps PageStep names."""

import re

from nustack.repository.page import PageStep
from nustack.rule import Rule


class TestPageStep:
    """The rule names the page steps by their whole headings, in order."""

    def test_is_named_whole_by_the_rule_in_order(self) -> None:
        named = re.findall(r"(### .+?) (?:and|section)", Rule.PAGE_STEPS)
        assert (named, [step.heading for step in PageStep]) == (
            ["### 1️⃣ Install", "### 2️⃣ Use"],
            ["### 1️⃣ Install", "### 2️⃣ Use"],
        )

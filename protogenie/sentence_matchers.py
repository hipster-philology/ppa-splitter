__all__ = ["SentenceMatcherProto", "SentenceRegexpMatcher", "SentenceEmptyLineMatcher"]

from abc import ABC
from xml.etree.ElementTree import Element
from typing import Optional, List

import regex as re


class SentenceMatcherProto:
    def match(self, headers: List[str], values: Optional[List[str]]):
        raise NotImplementedError()

    @classmethod
    def from_xml(cls, node: Element) -> "SentenceMatcherProto":
        if node.attrib["name"] == "regexp":
            return SentenceRegexpMatcher.from_xml(node.xpath("./sentence-marker")[0])
        return SentenceEmptyLineMatcher()


class SentenceRegexpMatcher(SentenceMatcherProto):
    def __init__(self, regexp: re.Regex, column: str):
        self.regexp: re.Regex = regexp
        self.column: str = column

    def match(self, headers: List[str], values: Optional[List[str]]):
        data = dict(zip(headers, values))
        return self.regexp.match(data[self.column]) is not None

    @classmethod
    def from_xml(cls, node: Element) -> "SentenceRegexpMatcher":
        return cls(
            regexp=re.compile(node.attrib["regexp"]),
            column=node.attrib["column"]
        )


class SentenceEmptyLineMatcher(SentenceMatcherProto):
    def __init__(self):
        pass

    def match(self, headers: List[str], values: Optional[List[str]]):
        return not values or len(headers) != len(values)

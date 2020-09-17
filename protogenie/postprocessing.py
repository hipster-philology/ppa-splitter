import tempfile
import math
import random
from abc import ABC, abstractmethod
from collections import namedtuple
from xml.etree.ElementTree import Element
import csv
from typing import List, ClassVar, Tuple, Dict, Optional, TYPE_CHECKING, Union

import regex as re

if TYPE_CHECKING:
    from .configs import CorpusConfiguration
from .sentence_matchers import SentenceMatcherProto, SentenceRegexpMatcher
Numeric = Union[int, float]


class PostProcessing(ABC):
    NodeName = "XML-NODE-LOCAL-NAME"  # Name of the node to match

    @abstractmethod
    def apply(self, file_path: str, config: "CorpusConfiguration"):
        raise NotImplementedError

    @abstractmethod
    def from_xml(cls, node: Element) -> ClassVar["PostProcessing"]:
        raise NotImplementedError

    @classmethod
    def match_config_node(cls, node: Element) -> bool:
        """ If the current node is representing the current object, returns True
        """
        return node.tag == cls.NodeName

    def _modify_line(self, header: List[str], values: Optional[List[str]],
                     file_path: str, config: "CorpusConfiguration"):
        raise NotImplementedError

    def _stop_chunk(self, line: Optional[Dict[str, str]]) -> bool:
        raise NotImplementedError

    def _chunk_modify_routine(self, file_path: str, config: "CorpusConfiguration"):
        raise NotImplementedError

    def _scan_chunks(self,
                     file_path: str, config: "CorpusConfiguration",
                     sentence_matcher: Optional[SentenceMatcherProto]) -> Tuple[int, int]:
        """ Analyzes the FILE for the number of chunks

        """
        chunks = 0
        tokens = 0
        with open(file_path) as file:
            for nb_line, line in enumerate(file):
                vals = line.strip().split(config.column_marker)

                if nb_line == 0:
                    header = vals
                    continue

                if len(header) == len(vals):
                    tokens += 1
                    if sentence_matcher and sentence_matcher.match(header, vals):
                        chunks += 1
                elif sentence_matcher:
                    chunks += sentence_matcher.match(header, None)

        return chunks, tokens

    def _single_line_modify_routine(self, file_path: str, config: "CorpusConfiguration"):
        header: List[str] = []
        temp = tempfile.TemporaryFile(mode="w+")  # 2

        try:
            with open(file_path) as file:
                for nb_line, line in enumerate(file):

                    if not line.strip():
                        temp.write(line)
                        self._modify_line(header, None, file_path, config)
                        continue

                    vals = line.strip().split(config.column_marker)

                    if nb_line == 0:
                        header = vals
                        temp.write(line)
                        continue

                    modified = self._modify_line(header, vals, file_path=file_path, config=config)
                    temp.write(
                        config.column_marker.join(
                            [modified[head] for head in header]
                        ) + "\n"
                    )

            with open(file_path, "w") as f:
                temp.seek(0)
                f.write(temp.read())
        finally:
            temp.close()  # 5


class ApplyTo:
    def __init__(self, source: str, target: List[str]):
        self.source: str = source
        self.target: List[str] = target

    @staticmethod
    def from_xml(apply_to_node: Element) -> "ApplyTo":
        return ApplyTo(
            source=apply_to_node.attrib["source"],
            target=[str(node.text).strip() for node in apply_to_node.findall("./target")]
        )


class Disambiguation(PostProcessing):
    NodeName = "disambiguation"

    def __init__(self, lemma_key: str, disambiguation_key: str, match_pattern: str,
                 default_value: str, glue: str, keep: bool = False):
        super(Disambiguation, self).__init__()
        self.lemma_key: str = lemma_key
        self.disambiguation_key: str = disambiguation_key
        self.match_pattern: re.Regex = re.compile(match_pattern)
        self.keep: bool = keep
        self.default_value: str = default_value
        self.glue: str = glue

    def apply(self, file_path: str, config: "CorpusConfiguration"):
        temp = tempfile.TemporaryFile(mode="w+")  # 2

        try:
            with open(file_path) as file:
                csv_reader = csv.reader(file, delimiter=config.column_marker)
                header: List[str] = []
                for nb_line, line in enumerate(csv_reader):  # The file should already have been open
                    if nb_line == 0:
                        temp.write(config.column_marker.join(line + [self.disambiguation_key]) + "\n")
                        header = line
                        continue
                    elif not line:
                        temp.write("\n")
                        continue
                    lines = dict(zip(header, line))

                    found = self.match_pattern.findall(lines[self.lemma_key])
                    if found:
                        lines[self.disambiguation_key] = found[0]
                        if not isinstance(found[0], str):
                            lines[self.disambiguation_key] = self.glue.join(found[0])
                        if not self.keep:  # If we do not keep the original value, we remove it
                            lines[self.lemma_key] = self.match_pattern.sub("", lines[self.lemma_key])
                    else:
                        lines[self.disambiguation_key] = self.default_value
                    temp.write(config.column_marker.join(list(lines.values())) + "\n")
            with open(file_path, "w") as f:
                temp.seek(0)
                f.write(temp.read())
        finally:
            temp.close()  # 5

    @classmethod
    def from_xml(cls, node: Element) -> "Disambiguation":
        return cls(
            lemma_key=node.attrib["source"],
            disambiguation_key=node.attrib["new-column"],
            match_pattern=node.attrib["matchPattern"],
            keep="keep" in node.attrib,
            default_value=node.attrib.get("default", "_"),
            glue=node.attrib.get("join", "|")
        )


class ReplacementSet(PostProcessing):
    """ Using a regular expression, replaces values in certain columns
    """
    NodeName = "replacement"

    def __init__(
            self, match_pattern: str, replacement_pattern: str,
            applies_to: List[ApplyTo]
    ):
        super(ReplacementSet, self).__init__()
        self.match_pattern: re.Regex = re.compile(match_pattern)
        self.replacement_pattern: str = replacement_pattern
        self.applies_to: List[ApplyTo] = applies_to

    def apply(self, file_path: str, config: "CorpusConfiguration"):
        temp = tempfile.TemporaryFile(mode="w+")
        try:
            with open(file_path) as file:
                csv_reader = csv.reader(file, delimiter=config.column_marker)
                header: List[str] = []
                for nb_line, line in enumerate(csv_reader):  # The file should already have been open
                    if nb_line == 0:
                        temp.write(config.column_marker.join(line) + "\n")
                        header = line
                        continue
                    elif not line:
                        temp.write("\n")
                        continue
                    lines = dict(zip(header, line))

                    for apply_to in self.applies_to:
                        if self.match_pattern.search(lines[apply_to.source]):
                            for target in apply_to.target:
                                # If source and target are the same, we simply replace source by target
                                if apply_to.source == target:
                                    lines[apply_to.source] = self.match_pattern.sub(
                                        self.replacement_pattern,
                                        lines[apply_to.source]
                                    )
                                else:  # Otherwise, we just set the target value using this value
                                    lines[target] = self.replacement_pattern

                    temp.write(config.column_marker.join(list(lines.values())) + "\n")
            with open(file_path, "w") as f:
                temp.seek(0)
                f.write(temp.read())
        finally:
            temp.close()  # 5

    @classmethod
    def from_xml(cls, node: Element) -> "ReplacementSet":
        return ReplacementSet(
            match_pattern=node.attrib["matchPattern"],
            replacement_pattern=node.attrib["replacementPattern"],
            applies_to=[ApplyTo.from_xml(apply_to) for apply_to in node.findall("applyTo")]
        )


class Skip(PostProcessing):
    """ If the matchPattern matches target column, the line is removed from the post-processed output
    """
    NodeName = "skip"

    def __init__(
            self, match_pattern: str, source: str
    ):
        super(Skip, self).__init__()
        self.match_pattern: re.Regex = re.compile(match_pattern)
        self.source: str = source

    def apply(self, file_path: str, config: "CorpusConfiguration"):
        temp = tempfile.TemporaryFile(mode="w+")  # 2

        try:
            with open(file_path) as file:
                csv_reader = csv.reader(file, delimiter=config.column_marker)
                header: List[str] = []
                for nb_line, line in enumerate(csv_reader):  # The file should already have been open
                    if nb_line == 0:
                        temp.write(config.column_marker.join(line) + "\n")
                        header = line
                        continue
                    elif not line:
                        temp.write("\n")
                        continue

                    lines = dict(zip(header, line))

                    # If it matches, we skip it
                    if self.match_pattern.search(lines[self.source]):
                        continue

                    temp.write(config.column_marker.join(list(lines.values())) + "\n")

            with open(file_path, "w") as f:
                temp.seek(0)
                f.write(temp.read())
        finally:
            temp.close()  # 5

    @classmethod
    def from_xml(cls, node: Element) -> "Skip":
        return Skip(
            match_pattern=node.attrib["matchPattern"],
            source=node.attrib["source"]
        )


class Clitic(PostProcessing):
    """ If the matchPattern matches target column, the line is removed from the post-processed output
    """
    NodeName = "clitic"

    Transfer = namedtuple("Transfer", ["col", "glue"])

    def __init__(
            self, match_pattern: str, source: str, glue: str, transfers: List[Tuple[str, bool]]
    ):
        super(Clitic, self).__init__()
        self.match_pattern: re.Regex = re.compile(match_pattern)
        self.source: str = source
        self.glue = glue
        _tr = {False: "", True: self.glue}
        self.transfers: List[Clitic.Transfer] = [
            Clitic.Transfer(key, _tr[has_glue])
            for key, has_glue in transfers
            if not print(key, has_glue)
        ]

    def apply(self, file_path: str, config: "CorpusConfiguration"):
        temp = tempfile.TemporaryFile(mode="w+")  # 2
        default = ("", "")
        try:
            with open(file_path) as file:
                csv_reader = csv.reader(file, delimiter=config.column_marker)
                header: List[str] = []
                sequence = []
                # [Int = Line to apply modifications to, Dict[Column name, Tuple[Glue, Value]]]
                modifications: List[Tuple[int, Dict[str, Tuple[str, str]]]] = []
                for nb_line, line in enumerate(csv_reader):  # The file should already have been open
                    if nb_line == 0:
                        temp.write(config.column_marker.join(line) + "\n")
                        header = line
                        continue
                    elif not line:
                        for target_line, modif in modifications:
                            sequence[target_line] = {
                                column: modif.get(column, default)[0].join(
                                    [value, modif.get(column, default)[1]]
                                )
                                for column, value in sequence[target_line].items()
                            }
                        temp.write("\n".join([
                            config.column_marker.join(list(l.values()))
                            for l in sequence
                        ]) + "\n")
                        sequence = []
                        modifications = []
                        continue

                    lines = dict(zip(header, line))

                    # If it matches, we give it to the previous / original line
                    if self.match_pattern.match(lines[self.source]):
                        modifications.append(
                            (
                                len(sequence) - 1 - len(modifications),
                                {key: (keep, lines[key]) for (key, keep) in self.transfers}
                            )
                        )
                        continue

                    # config.column_marker.join(list(lines.values()))
                    sequence.append(lines)

            with open(file_path, "w") as f:
                temp.seek(0)
                f.write(temp.read())
        finally:
            temp.close()  # 5

    @classmethod
    def from_xml(cls, node: Element) -> "Clitic":
        return cls(
            match_pattern=node.attrib["matchPattern"],
            source=node.attrib["source"],
            glue=node.attrib["glue_char"],
            transfers=[
                (
                    tr.text,
                    tr.attrib.get("no-glue-char", "false").lower() == "false"
                )
                for tr in node.findall("transfer")
            ]
        )


class Capitalize(PostProcessing):
    """ Applies capitalization strategies to content
    """
    NodeName = "capitalize"
    Marker: str = "🨁"  # NEUTRAL CHESS QUEEN
    RE_Upper: re.Regex = re.compile("(\p{Lu})")

    def __init__(self, first_word: Numeric, first_letters: Numeric,
                 column_token: str,
                 column_lemma: Optional[str] = None,
                 apply_unicode_marker: bool = False,
                 sentence_matcher: Optional[SentenceMatcherProto] = None):

        self.first_word: Numeric = first_word
        self.first_letters: Numeric = first_letters

        self.column_token: str = column_token
        self.column_lemma: Optional[str] = column_lemma
        self.apply_unicode_marker: bool = apply_unicode_marker
        self.sentence_matcher: Optional[SentenceMatcherProto] = sentence_matcher
        self.first_word_state: bool = True  # Variable representing the current status
        # (True = next word is a first word)

        self._files_chunks: Dict[str, List[bool]] = {}
        self._files_tokens: Dict[str, List[bool]] = {}

    @staticmethod
    def parse_when(value: str, ratio: Optional[str]) -> Numeric:
        if value == "always":
            return 1
        elif value == "never":
            return 0
        elif value == "random":
            return 0.5
        elif ratio:
            try:
                if 1.0 > float(ratio) > .0:
                    return float(ratio)
            except:
                raise ValueError("Your ration value is probably wrong. They must be < 1.0 (Found: {})".format(ratio))
        raise ValueError("Invalid parameters for a ratio or an application")

    @classmethod
    def parse_node_including_when(cls, node: Element, name: str) -> Tuple[Numeric, Optional[Element]]:
        target = node.findall("./{name}".format(name=name))
        if target:
            return cls.parse_when(target[0].attrib["when"], target[0].attrib.get("ratio")), target[0]
        return 0, None

    def _modify_line(self, header: List[str], values: Optional[List[str]],
                     file_path: str, config: "CorpusConfiguration") -> Dict[str, str]:
        if self.first_word and self.sentence_matcher.match(header, values):
            self.first_word_state = True
            return dict(zip(header, values))

        if not values or len(header) != len(values):
            return {}

        line = dict(zip(header, values))

        # Sentence starts
        if self.first_word > .0 and self.first_word_state and self._files_chunks[file_path].pop():
            line[self.column_token] = line[self.column_token].capitalize()
            # Need to pop tokens as well
            if self.first_letters:
                self._files_tokens[file_path].pop()
        elif self.first_letters > .0 and self._files_tokens[file_path].pop():
            line[self.column_token] = line[self.column_token].capitalize()

        line[self.column_token] = self.RE_Upper.sub(self._replace_caps, line[self.column_token])

        self.first_word_state = False
        return line

    def _replace_caps(self, value):
        return value.group().lower()+self.Marker

    @staticmethod
    def _transform_to_bool_list(count: int, ratio: Numeric) -> List[bool]:
        if ratio == 1.0:
            return [True] * count
        elif ratio == .0:
            return [False] * count
        else:
            positives = min(round(count * ratio), count)
            negatives = count - positives
            out = [True] * positives + [False] * negatives
            random.shuffle(out)
            return out

    def apply(self, file_path: str, config: "CorpusConfiguration"):
        # We scan the files
        chunks, tokens = self._scan_chunks(file_path, config, sentence_matcher=self.sentence_matcher)

        # We store the dispatch of booleans
        if self.first_word > .0:
            self._files_chunks[file_path] = self._transform_to_bool_list(chunks, self.first_word)
        if self.first_letters > .0:
            self._files_tokens[file_path] = self._transform_to_bool_list(tokens, self.first_letters)

        self._single_line_modify_routine(file_path=file_path, config=config)

    @classmethod
    def from_xml(cls, node: Element) -> "Capitalize":
        first_word, first_word_elem = cls.parse_node_including_when(node, "first-word")
        first_letters, _ = cls.parse_node_including_when(node, "first-letters")
        sentence_marker = None
        if first_word != .0:
            try:
                sentence_marker = SentenceMatcherProto.from_xml(
                    first_word_elem.findall("./sentence-marker")[0]
                )
            except IndexError:
                print("You forgot to use a sentence marker.")
                raise Exception

        return cls(
            first_word=first_word,
            first_letters=first_letters,
            sentence_matcher=sentence_marker,
            apply_unicode_marker=node.attrib.get("utf8-marker-for-caps", "true").lower() == "true",
            column_token=node.attrib["column-token"],
            column_lemma=node.attrib.get("column-lemma")
        )

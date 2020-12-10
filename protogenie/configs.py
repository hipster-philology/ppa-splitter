from typing import Dict, Optional, Any, Type, List
import os.path
import lxml.etree as ET
from copy import deepcopy

from .splitters import RegExpSplitter, LineSplitter, TokenWindowSplitter, FileSplitter, _SplitterPrototype
from .reader import Reader
from .postprocessing import Disambiguation, ReplacementSet, Skip, PostProcessing, Clitic, Capitalize
from .toolbox import RomanNumeral
import datetime
from dataclasses import dataclass
Splitter = Type[_SplitterPrototype]

PostProcessingClasses = [Disambiguation, ReplacementSet, Skip, RomanNumeral, Clitic, Capitalize]


@dataclass
class Output:
    """ Details about output"""
    header: List[str]
    column_marker: str
    readable_column_marker: str


class CorpusConfiguration:
    SPLITTERS = {
        "empty_line": LineSplitter,
        "regexp": RegExpSplitter,
        "token_window": TokenWindowSplitter,
        "file_split": FileSplitter
    }

    UNIT_NAMES = {
        "empty_line": "chunks",
        "regexp": "sentences",
        "token_window": "token-windows",
        "file_split": "tokens"
    }

    COLUMN_SPECIAL_MARKERS = {
        "TAB": "\t"
    }
    REVERSE_COLUMN_SPECIAL_MARKERS = {
        character: name
        for name, character in COLUMN_SPECIAL_MARKERS.items()
    }

    def __init__(self,
                 reader: Reader,
                 splitter: str = "sentence_marker", **spliter_options):
        """ Initiate a configuration which will allow file-basis dispatching

        :param splitter: The splitter to use (Default : sentence_marker)
        :param sentence_markers: Characters to use for separating on sentence marker
        :param each_n_words:
        :param column_marker: Marker for columns in files
        """
        self.reader: Reader = reader
        self.splitter_name: str = splitter

        _spliter_options: Dict[str, Any] = spliter_options

        # Some characters are awful to replicate in YAML, that's why
        #  we have a dictionary of simplified names
        _spliter_options["column_marker"] = self.COLUMN_SPECIAL_MARKERS.get(
            _spliter_options["column_marker"],
            _spliter_options["column_marker"]
        )

        self.column_marker: str = _spliter_options["column_marker"]

        # We set up the splitter
        splitter_class: Optional[Type] = self.SPLITTERS.get(self.splitter_name, None)
        if splitter_class is None:
            raise ValueError("Splitter '{}' is not in the acceptable list: {}".format(
                self.splitter_name, ", ".join(list(self.SPLITTERS.keys()))
            ))
        # Initialize the splitter
        self.splitter: _SplitterPrototype = splitter_class(**_spliter_options)

    def __repr__(self):
        return "<corpus column_marker='{column}'>{splitter}</corpus>".format(
            column=self.column_marker.replace("\t", "TAB"),
            splitter=self.splitter
        )

    @property
    def unit_name(self):
        return self.UNIT_NAMES[self.splitter_name]

    def splitter_reset(self):
        """ This function can be useful to reset a splitter in between passes
        """
        self.splitter.reset()

    def build_dataset_dispatch_list(self, units_count, test_ratio=0.2, dev_ratio=0.0001):
        """ Build a list of dataset target that will be used by the dispatching loop


        :param units_count: Number of units to dispatch (either sentence or dispatch depending on self.splitter)
        :param test_ratio: Ratio of data to be put in test
        :param dev_ratio: Ratio of data to be put in dev
        :return: List of dataset name targets (list of "train", "test" and "dev")
        """
        return self.splitter.dispatch(units_count, test_ratio=test_ratio, dev_ratio=dev_ratio)


class ProtogenieConfiguration:
    def __init__(self,
                 path: str,
                 corpora: Dict[str, CorpusConfiguration],
                 output: Output,
                 memory: Optional[str] = None,
                 postprocessings: List[PostProcessing] = None,
                 **kwargs
                 ):
        self.path: str = path
        self.dir: str = os.path.abspath(os.path.dirname(path))

        self.memory: Optional[str] = memory
        self.corpora: Dict[str, CorpusConfiguration] = corpora
        self.postprocessings: List[PostProcessing] = postprocessings or []
        self.output: Output = output

    @classmethod
    def from_xml(cls, filepath: str) -> "ProtogenieConfiguration":
        with open(filepath) as f:
            xml = ET.parse(f)
            inc = ET.XInclude()
            inc(xml.getroot())
        kwargs = {}

        # Get readers
        default_reader = Reader.from_xml(xml.find("./default-header/header"), default=None)

        col = xml.find("./output").attrib["column_marker"]
        header_node = xml.find("./output/header")
        if not header_node or header_node.get("name", "default") == "default":
            header = [mapped or key for key, mapped in default_reader._keys]
        else:
            header = [node.text.strip() for node in xml.findall("./output/header/key")]
        output = Output(
            column_marker=col.replace("TAB", "\t"),
            readable_column_marker=col,
            header=header
        )

        # Parse corpora configurations
        corpora = {}
        for corpus in xml.findall("./corpora/corpus"):
            corpora[corpus.get("path")] = CorpusConfiguration(**{
                "column_marker": corpus.get("column_marker"),
                "splitter": corpus.find("splitter").get("name"),
                "reader": Reader.from_xml(corpus.find("./header"), default=default_reader),
                **{key: value for key, value in corpus.find("splitter").attrib.items() if key != "name"}
            })

        # Check options
        if len(xml.findall("./memory")):
            kwargs["memory"] = xml.find("./memory").get("path")

            kwargs["memory"] = kwargs["memory"].replace(
                "$file$", os.path.splitext(os.path.basename(filepath))[0]
            ).replace(
                "$date$", datetime.datetime.now().strftime("%y-%m-%d_%H-%M-%S")
            )

        kwargs["postprocessings"] = []
        for element in xml.findall("./postprocessing"):
            for child in element:
                for post_processing_class in PostProcessingClasses:
                    if post_processing_class.match_config_node(child):
                        kwargs["postprocessings"].append(post_processing_class.from_xml(child))

        return cls(path=filepath, corpora=corpora, output=output, **kwargs)

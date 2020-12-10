from typing import List, Tuple, Dict, Union, Optional
from xml.etree.ElementTree import Element


class Reader(object):
    @property
    def init_params(self):
        return {"reader_type": self.reader_type, "keys": self._keys, "column_marker": self.column_marker}

    def __init__(self, reader_type: str, keys: List[Tuple[str, Optional[str]]], column_marker: str = None):
        self.map_to: Dict[Union[int, str], str] = {}
        self._keys = keys
        self.column_marker: str = column_marker
        self.reader_type: str = reader_type
        self._header: List[str] = []

        self._reverse_map = {}

        if self.reader_type == "order":
            self.map_to = {int(key): mapped for key, mapped in keys if mapped}
            self._header = [
                self.map_to.get(item, "UNK"+str(item))
                for item in range(max(self.map_to.keys())+1)
            ]
        elif self.reader_type == "explicit":
            self.map_to = {key: mapped or key for key, mapped in keys}

    def get_column(self, line: List[str], column: str) -> str:
        """ Given a list of tokens, chez if we have it in our header"""
        if column in self._reverse_map:
            return line[self._reverse_map[column]]

        for pos, (value, key) in enumerate(zip(line, self.header)):
            if key == column:
                self._reverse_map[column] = pos
                return value

    @property
    def has_header(self):
        return self.reader_type == "explicit"

    @classmethod
    def from_xml(cls, xml_node: Element, column_marker: Optional[str] = None, default: Optional["Reader"] = None) -> "Reader":
        reader_type = xml_node.attrib["type"]
        if reader_type == "default":
            if not default:
                raise Exception("Not default reader was passed but one was asked by the configuration.")
            params = default.init_params
            params["column_marker"] = column_marker
            return cls(**params)
        _map = [(key.text.strip(), key.get("map-to")) for key in xml_node.findall("./key") if key.text]
        return cls(reader_type=reader_type, keys=_map, column_marker=column_marker)

    def set_header(self, line: str) -> List[str]:
        self._header = [
            self.map_to[key]
            for key in line.strip().split(self.column_marker)
            if key and key in self.map_to
        ]
        return self._header

    @property
    def header(self):
        return self._header

    def __repr__(self):
        return "<Reader type='{}' keys=[{}] from=[{}] />".format(
            self.reader_type,
            ", ".join(self.map_to.values()),
            ", ".join(list(map(str, self.map_to.keys())))
        )

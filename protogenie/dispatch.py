from .io_utils import add_sentence, get_name
from .configs import CorpusConfiguration, ProtogenieConfiguration
from dataclasses import dataclass
from typing import Dict, Optional, List, Set, Tuple
from .splitters import LineSplitter
import glob
import os
import math
import csv


__all__ = ["split_files", "files_from_memory", "ConfigError"]


class ConfigError(Exception):
    """ Error when a configuration has been wrong"""


@dataclass
class _Range:
    """Just a class to deal with typing. End is the end of the range, dataset is [train|dev|test]"""
    end: int
    dataset: str


@dataclass
class _CorpusDispatched:
    """ Item that contains informations about dispatching

    Using dataclass mainly for typing"""
    config: CorpusConfiguration
    lines: Dict[int, _Range]


################
# Main Functions
################


def split_files(
        config: ProtogenieConfiguration, output_folder: str, dev_ratio: float, test_ratio: float,
        verbose: bool = True, no_split: bool = False):
    """ Dispatch sentence for each file in files

    :param config: Configuration for PPA Splitter
    :param output_folder: Folder where the data should be saved
    :param dev_ratio: Ratio of data to put in dev
    :param test_ratio: Ratio of data to put in test
    :param verbose: Verbosity (Adds some print during process)
    :param no_split: Do not apply splitting

    :yield: File, Dispatch stats about file
    """

    memory, memory_file = None, None
    if config.memory:
        memory_file = open(config.memory, "w")
        memory = csv.writer(memory_file)

    # For each file
    for unix_path, current_config in config.corpora.items():
        unix_path = os.path.join(config.dir, unix_path)
        for file in glob.glob(unix_path):
           yield from _single_file_dispatch(
               file, current_config=current_config, memory=memory,
               dev_ratio=dev_ratio, test_ratio=test_ratio, output_folder=output_folder,
               config=config, verbose=verbose, no_split=no_split
           )

    if memory:
        memory_file.close()


def files_from_memory(
        config: ProtogenieConfiguration, output_folder: str, memory_file: str,
        verbose: bool = True, dev_ratio: float = None, test_ratio: float = None):
    """ Regenerate a corpus using the same previously selected lined but potentially
    adding files and different post-processing

    :param config: Configuration
    :param output_folder: Directory where to save files
    :param memory_file: Memory file that holds lines to dispatch
    :param verbose: Whether to print stuff
    :param dev_ratio: Dev Ratio
    :param test_ratio: Test ratio
    """
    memory = open(memory_file)
    memory_reader = csv.reader(memory)

    dispatcher: Dict[str, _CorpusDispatched] = {
        os.path.realpath(real_path): _CorpusDispatched(config=corpus_config, lines={})
        for unix_path, corpus_config in config.corpora.items()
        for real_path in glob.glob(os.path.join(config.dir, unix_path))
    }

    # For each file, we build a map of the lines that needs to be dispatched
    for line in memory_reader:
        if not line:
            continue
        current_file, line_range, dataset_target = line

        real_path = os.path.realpath(current_file)
        if real_path in dispatcher:
            start, end = tuple(map(int, line_range.split("-")))
            dispatcher[real_path].lines[start] = _Range(end=end, dataset=dataset_target)
    memory.close()

    new_files = []
    for file, dispatching in dispatcher.items():
        if not dispatching.lines:
            new_files.append((file, dispatching.config))
            pass

        # We set up a dictionary of token count to print nice
        #  information later
        training_tokens = {"test": 0, "dev": 0, "train": 0}

        current_config = dispatching.config

        header_line = []
        created_files = set()
        sentence = []
        blanks = 0
        current_set: Optional[_Range] = None

        with open(file) as f:
            for line_no, line in enumerate(f):
                if line_no == 0:
                    if current_config.reader.has_header:
                        header_line = current_config.reader.set_header(line)
                        continue
                    else:
                        header_line = current_config.reader.header
                elif not line.strip() and not isinstance(current_config.splitter, LineSplitter):
                    # Only count is we already have written or the sentence writing has started
                    if len(sentence) > 0:
                        blanks += 1
                    continue

                if line_no in dispatching.lines:                  # We begin a set
                    current_set = dispatching.lines[line_no]
                    sentence.append(line)
                elif current_set and line_no != current_set.end:  # We are in the set
                    sentence.append(line)
                elif current_set and line_no == current_set.end:  # We are at the end of the set
                    sentence.append(line)
                    blanks = 0  # ToDo: Blanks are not really taken into account here...
                    sentence = [x for x in sentence if x.strip()]
                    add_sentence(
                        output_folder=output_folder,
                        dataset=current_set.dataset,
                        filename=file,
                        sentence=sentence,
                        source_marker=current_config.column_marker,
                        output_marker=config.output.column_marker
                    )
                    training_tokens[current_set.dataset] += len(sentence)
                    sentence = []

            # Finally, if there is something remaining
            if len(sentence) and current_set:
                add_sentence(
                    output_folder=output_folder,
                    dataset=current_set.dataset,
                    filename=file,
                    sentence=sentence,
                    source_marker=current_config.column_marker,
                    output_marker=config.output.column_marker
                )
                training_tokens[current_set.dataset] += len(sentence)

        # Add the header to the files
        created_files.update(
            _add_header(
                output_folder=output_folder, training_tokens=training_tokens, header_line=header_line,
                current_config=current_config, file=file
            )
        )

        yield file, training_tokens

        if config.postprocessings:
            for post_processings in config.postprocessings:
                for output_file in created_files:
                    post_processings.apply(output_file, current_config)

    if new_files:
        # We have new files, we need to deal with them per usual
        if not test_ratio:
            raise ConfigError("Ratios were not given and we have a new file.")

        for file, current_config in new_files:
            yield from _single_file_dispatch(
                config=config,
                dev_ratio=dev_ratio,
                test_ratio=test_ratio,
                current_config=current_config,
                verbose=verbose,
                file=file,
                output_folder=output_folder
            )


def glue(config: ProtogenieConfiguration, output_folder: str,
         verbose: bool = True, reduce: Optional[float] = None, prefix: str = ""):
    """

    :param config:
    :param output_folder:
    :param verbose:
    :param reduce: [Optional] Take only a portion of a float
    :return: Generator[data_type, filename, nb_chunks, nb_lines]
    """
    def write_sentence(sents: List[List[str]], dataset):
        dataset.write("\n".join(config.output.column_marker.join(sent) for sent in sents)+"\n\n") # 2 new lines

    for dataset_type in ["train", "test", "dev"]:
        cur_dir = os.path.join(output_folder, dataset_type)

        out = os.path.join(output_folder, prefix + dataset_type + ".tsv")
        out = open(out, "w")
        out.write(config.output.column_marker.join(config.output.header)+"\n")

        for _, _, files in os.walk(cur_dir, topdown=False):
            for file in files:
                basename = os.path.basename(file)
                tokens = [0]

                # Output files necessarly have headers and empty lines as markers
                with open(os.path.join(cur_dir, file)) as f:
                    sentences = []
                    sentence = []
                    for line_numb, line in enumerate(f.readlines()):
                        line = line.strip()
                        # If we met the header
                        if line_numb == 0:
                            cols = line.split(config.output.column_marker)
                            header_map = [cols.index(head) for head in config.output.header]
                            continue

                        # If we have a sentence
                        if not line and sentence:
                            sentences.append(sentence)
                            sentence = []
                            tokens.append(0)
                            continue

                        mapped = line.split(config.output.column_marker)
                        if not "".join(mapped).strip():
                            continue
                        try:
                            mapped = [mapped[index] for index in header_map]
                        except IndexError:
                            raise ValueError(f"Line {line_numb} failing in {file}: {mapped}")
                        tokens[-1] += 1
                        sentence.append(mapped)

                    if sentence:
                        sentences.append(sentence)

                    max_int = len(sentences)
                    if reduce:# and dataset_type == "train":
                        max_int = math.ceil(reduce * max_int)

                    for sentence in sentences[:max_int]:
                        #if dataset_type == "dev":
                        #    print(sentence)
                        write_sentence(sentence, out)

                yield dataset_type, basename, len(sentences[:max_int]), sum(tokens[:max_int])

        out.close()
    return []

##################
# Shared functions
##################


def _preview(file: str, current_config: CorpusConfiguration) -> Tuple[List[str], int, int, int]:
    # We count things in the file
    unit_counts = 0
    empty_lines = 0
    header_line = []

    if not current_config.reader.has_header:
        header_line = current_config.reader.header

    with open(file) as f:
        for line_no, line in enumerate(f):
            if line_no == 0:
                if current_config.reader.has_header:
                    header_line = current_config.reader.set_header(line)
                    continue

            if line_no == 0 and current_config.reader.has_header:
                continue  # Skip the first line in count if we have a header
            unit_counts += int(current_config.splitter(line, reader=current_config.reader            ))
            empty_lines += int(not bool(line.strip()))  # Count only lines if they are empty

    return header_line, unit_counts, empty_lines, line_no - int(current_config.reader.has_header) - empty_lines + 1


def _single_file_dispatch(
        file: str, current_config: CorpusConfiguration,
        config: ProtogenieConfiguration, output_folder: str, dev_ratio: float, test_ratio: float,
        verbose: bool = True, memory=None, no_split: bool = False
):
    # We do two passes here
    #  1. The first one is used to collect informations about the file. In order to not keep data in memory,
    #     we iterate over it and count the number of real lines + the number of sentences.
    #     Sentences are counted on the base of the Configuration.split function
    #  2. We read the file again and dispatch according to the ratio and the data we got before
    #      Note : We use .pop(0) to move from start to end. If we have one day a performance issue
    #      we might want to move to a yield system
    #
    # This method is slower but allows for memory efficiency.

    header_line, unit_counts, empty_lines, lines = _preview(file, current_config)

    if verbose:
        if no_split is True:
            print("Not splitting file {filename}".format(filename=file))
        else:
            print("{unit_count} {unit_name} to dispatch in {filename} ({lines} full, {lines_empty} empty)".format(
                filename=file, unit_name=current_config.unit_name, unit_count=unit_counts,
                lines_empty=empty_lines, lines=lines
            ))

    # We set up numbers based on the ratio
    # In order to do that, we get to use
    if no_split is False:
        target_dataset = current_config.build_dataset_dispatch_list(
            units_count=unit_counts,
            test_ratio=test_ratio,
            dev_ratio=dev_ratio
        )

        # We set up a dictionary of token count to print nice
        #  information later
        training_tokens = {"test": 0, "dev": 0, "train": 0}
    else:
        training_tokens = {"output": 0}

    # ToDo: When file splitter, the number of lines should be passed here probably ? Or is reset the issue ? ...

    current_config.splitter.reset()
    if not no_split:
        current_config.splitter.set_targets(target_dataset)

    created_files = set()

    with open(file) as f:
        sentence = []
        blanks = 0
        for line_no, line in enumerate(f):
            if line_no == 0 and current_config.reader.has_header:
                continue
            elif not line.strip() and not isinstance(current_config.splitter, LineSplitter):
                # Only count is we already have written or the sentence writing has started
                if len(sentence) > 0:
                    blanks += 1
                continue

            sentence.append(line)
            if current_config.splitter(line, reader=current_config.reader):
                if no_split:
                    dataset = "output"
                else:
                    dataset = target_dataset.pop(0)

                if memory:
                    memory.writerow([file, "{}-{}".format(line_no - len(sentence) + 1 - blanks, line_no), dataset])
                    blanks = 0

                sentence = [x for x in sentence if x.strip()]
                add_sentence(
                    output_folder=output_folder,
                    dataset=dataset,
                    filename=file,
                    sentence=sentence,
                    source_marker=current_config.column_marker,
                    output_marker=config.output.column_marker,
                    subfolder=not no_split
                )
                training_tokens[dataset] += len(sentence)
                sentence = []

        # Finally, if there is something remaining
        if len(sentence):
            try:
                dataset = target_dataset.pop(0)
                # print("last dataset ?")
            except Exception:
                if no_split:
                    dataset = "output"
                else:
                    dataset = "train"

            if memory:
                memory.writerow([file, "{}-{}".format(line_no - len(sentence) + 1 - blanks, line_no), dataset])

            add_sentence(
                output_folder=output_folder,
                dataset=dataset,
                filename=file,
                sentence=sentence,
                source_marker=current_config.column_marker,
                output_marker=config.output.column_marker,
                subfolder=not no_split
            )
            training_tokens[dataset] += len(sentence)

    created_files.update(
        _add_header(
            output_folder=output_folder, training_tokens=training_tokens, header_line=header_line,
            current_config=current_config, file=file,
            subfolder=not no_split
        )
    )

    yield file, training_tokens

    if config.postprocessings:
        for post_processings in config.postprocessings:
            for output_file in created_files:
                post_processings.apply(output_file, current_config)


def _add_header(output_folder: str, file: str,
                training_tokens: Dict[str, int], current_config: CorpusConfiguration,
                header_line: List[str],
                subfolder: bool = True
                ) -> Set[str]:
    files = set()
    for dataset, tokens in training_tokens.items():
        if tokens:
            if subfolder:
                trg = get_name(output_folder, dataset, file)
            else:
                trg = get_name(output_folder, "", file)
            files.add(trg)  # We add the file to the one we created
            with open(trg) as f:
                content = f.read()
            with open(trg, "w") as f:
                f.write(current_config.column_marker.join(header_line)+"\n"+content)
    return files

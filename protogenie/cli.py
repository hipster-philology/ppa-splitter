from argparse import ArgumentParser
import os
import shutil
from typing import Optional

from .configs import ProtogenieConfiguration
from .dispatch import split_files, files_from_memory, glue
from .cli_utils import check_ratio

import click


@click.group()
def main():
    """Protogeneia is a tool to preprocess and harmonize datasets in NLP tasks. Might be useful for other stuff too
    as long as you have TSV/CSV ;)"""
    pass


@main.command("get-scheme")
@click.argument("dest", type=click.Path(file_okay=True, dir_okay=True), default="./scheme.rng")
def cli_scheme(dest):
    """Copy the schema file to [WHERE]"""
    import os
    import shutil
    here = os.path.abspath(os.path.dirname(__file__))
    schema = os.path.join(here, "schema.rng")
    shutil.copy(schema, dest)
    click.echo("Copied to {}".format(os.path.abspath(dest)))


@main.command("build")
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("--output", default="./output", type=str, help="Directory where the output should be built")
@click.option("-n", "--no-split", default=False, is_flag=True, help="Does not apply splitting to files")
@click.option("-c", "--clear", default=False, is_flag=True, help="Clear the output directory")
@click.option("-t", "--train", "train", default=0.8, type=float, help="Percentage of data to use for training")
@click.option("-d", "--dev", "dev", default=0., type=float, help="Percentage of data to use for dev set")
@click.option("-e", "--test", "test", default=0.2, type=float, help="Percentage of data to use for test set")
@click.option("-v", "--verbose", default=False, is_flag=True, help="Print text level stats")
def cli_build(file, output="./output", no_split=False, clear=False, train=0.8, dev=.0, test=0.2, verbose=False):
    """ Uses [FILE] to split and pre-process a training corpus for NLP Tasks. File should follow the schema, see
    protogeneia get-scheme"""

    if clear:
        confirm_message = "Are you sure you want to remove data in {} ? [y/n]\t>\t".format(output)

        if click.confirm(confirm_message):
            click.echo("\tRemoving data in {}".format(output))
            shutil.rmtree(output, ignore_errors=True)
        else:
            print("\tData were not removed")
    if no_split:
        train, test, dev = 1, 0, 0

    dispatch(
        config=file,
        train=train,
        test=test,
        dev=dev,
        output_dir=output,
        verbose=verbose
    )


@main.command("rebuild")
@click.argument("file", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("memory", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.option("--output", default="./output", type=str, help="Directory where the output should be built")
@click.option("-c", "--clear", default=False, is_flag=True, help="Clear the output directory")
@click.option("-d", "--dev", "dev", default=0., type=float,
              help="[New file only] Percentage of data to use for dev set")
@click.option("-e", "--test", "test", default=None, type=float,
              help="[New file only] Percentage of data to use for test set")
def cli_rebuild(file, memory, output, clear=False, dev=.0, test=0.2):
    """Given [MEMORY] file, uses [FILE] config file to generate a new corpus

    This method detects new files and treat them if --test and --dev are given
    """

    if clear:
        confirm_message = "Are you sure you want to remove data in {} ? [y/n]\t>\t".format(output)

        if click.confirm(confirm_message):
            click.echo("\tRemoving data in {}".format(output))
            shutil.rmtree(output, ignore_errors=True)
        else:
            print("\tData were not removed")

    from_memory(
        config=file,
        memory_file=memory,
        test_ratio=test,
        dev_ratio=dev,
        output_dir=output
    )


@main.command("concat")
@click.argument("config", type=click.Path(exists=True, file_okay=True, dir_okay=False))
@click.argument("output",  type=click.Path(exists=True, file_okay=False, dir_okay=True))
@click.option("-r", "--reduce", type=click.FLOAT, default=None, help="Reduce training corpus to the given percentage")
@click.option("-p", "--prefix", type=click.STRING, default="", help="Prefix for output files")
@click.option("-v", "--verbose", default=False, is_flag=True, help="Print text level stats")
def cli_concat(config, output, reduce, verbose, prefix):
    """Given [MEMORY] file, uses [FILE] config file to generate a new corpus

    This method detects new files and treat them if --test and --dev are given
    """
    concat(config, output, verbose=verbose, reduce=reduce, prefix=prefix)


def dispatch(
        train: float, test: float, dev: float, config: str, output_dir: str,
        verbose=False, concat: bool = False) -> ProtogenieConfiguration:
    """

    :param train:
    :param test:
    :param dev:
    :param config:
    :param output_dir:
    :param verbose:
    :param concat:
    :return: PPAConfiguration for test purposes
    """

    train, test, dev = check_ratio(train, test, dev)
    config = ProtogenieConfiguration.from_xml(config)
    no_split = sorted([train, test, dev]) == [0, 0, 1]

    os.makedirs(output_dir, exist_ok=True)
    if not no_split:  # No split
        for subset in ["dev", "test", "train"]:
            os.makedirs(os.path.join(output_dir, subset), exist_ok=True)

    print("=============")
    print("Processing...")
    # I run over each files
    for file, ratios in split_files(output_folder=output_dir, verbose=verbose, dev_ratio=dev, test_ratio=test,
                                    config=config, no_split=no_split):

        print("{} has been transformed".format(file))
        for key, value in ratios.items():
            if value:
                print("\t{} tokens in {} dataset".format(value, key))

    return config


def from_memory(memory_file: str, config: str, output_dir: str,
                dev_ratio: float = None, test_ratio: float = None) -> ProtogenieConfiguration:
    config = ProtogenieConfiguration.from_xml(config)

    os.makedirs(output_dir, exist_ok=True)
    for subset in ["dev", "test", "train"]:
        os.makedirs(os.path.join(output_dir, subset), exist_ok=True)

    for file, ratios in files_from_memory(config=config, memory_file=memory_file, output_folder=output_dir,
                                          dev_ratio=dev_ratio, test_ratio=test_ratio):
        print("{} has been transformed".format(file))
        for key, value in ratios.items():
            if value:
                print("\t{} tokens in {} dataset".format(value, key))

    return config


def concat(config: str, output_dir: str, verbose: bool = True, reduce: Optional[float] = None,
           prefix: str = ""
           ) -> ProtogenieConfiguration:
    if reduce is not None:
        if reduce > 1 or reduce < 0.:
            raise click.BadParameter("Reduce should be in the range ]0:1]")
    config = ProtogenieConfiguration.from_xml(config)
    dataset = None

    max_len = 50
    template = '    {:'+str(max_len)+'s} {:>10d} {:>10d}'
    chunks_lines = {}
    for data_type, filename, nb_chunks, nb_lines in glue(
            config=config, output_folder=output_dir, verbose=verbose, reduce=reduce, prefix=prefix):
        if dataset != data_type:
            if dataset in chunks_lines:
                click.echo("# {}'s statistics".format(dataset))
                click.echo("Chunks: {:>15,d}".format(chunks_lines[dataset][0]))
                click.echo("Tokens: {:>15,d}".format(chunks_lines[dataset][1]))
            if verbose:
                click.echo("\n========\n{}\n".format(data_type))
                click.echo(template.replace("d", "s").format("File", "Chunks", "Tokens"))
            dataset = data_type
            chunks_lines[data_type] = [0, 0]
        if verbose:
            click.echo(template.format(filename[:max_len], nb_chunks, nb_lines))
        chunks_lines[data_type][0] += nb_chunks
        chunks_lines[data_type][1] += nb_lines

    click.echo("# {}'s statistics".format(dataset))
    click.echo("Chunks: {:>15,d}".format(chunks_lines[dataset][0]))
    click.echo("Tokens: {:>15,d}".format(chunks_lines[dataset][1]))

    total_chunks, total_lines = sum([v[0] for v in chunks_lines.values() if v[0]]), \
                                sum([v[1] for v in chunks_lines.values() if v[1]])

    click.echo("++++++++++++++\nSummary:")
    for dataset in chunks_lines:
        click.echo("{}: {:.2f} of chunks, {:.2f} of tokens".format(
            dataset,
            chunks_lines[dataset][0] / total_chunks * 100,
            chunks_lines[dataset][1] / total_lines * 100
        ))
    return config

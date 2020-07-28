import argparse
import logging
import sys
import os
import inspect
import re


current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from entity import Entity

logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)


def get_pretty(line):
    new_line = line
    for m in re.finditer(Entity.ANNOTATED_ENTITY_PATTERN, line):
        category = m.group(2)
        if category != "unknown":
            primary, secondary = category.split("/")
            start_ind_primary = primary.find(":") + 1
            if start_ind_primary == 0:
                start_ind_primary = primary.find("_") + 1
            primary = primary[start_ind_primary:].replace(" ", "_")
            category = primary
        repl_str = "[" + m.group(1) + "|" + category + "|" + m.group(3) + "]"
        new_line = new_line.replace(m.group(0), repl_str)
    return new_line


def main(args):
    if args.debug:
        logger.setLevel(logging.DEBUG)

    logger.info("Pretty print category for entities in %s (i.e. print only primary type)." % args.input_file)
    output_file = open(args.output_file, "w", encoding="utf8")
    with open(args.input_file, "r", encoding="utf8") as file:
        for line in file:
            new_line = get_pretty(line)
            output_file.write(new_line)
    logger.info("Done. Output written to %s" % args.output_file)


if __name__ == "__main__":
    # Handle command line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")

    parser.add_argument("-i", "--input_file", type=str, required=True,
                        help="Input file")

    parser.add_argument("-o", "--output_file", type=str, default=None,
                        help="Output file. If not provided, output will be written to stdout")

    main(parser.parse_args())

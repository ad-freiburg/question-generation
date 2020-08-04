"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Convert own linker entity output to category format [<QID>:<name>|<category>|<original>].
"""

import logging
import re
import argparse
import os
import sys
import inspect

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from entity import Entity
import config

# Set up the logger
logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

NAME_TO_QID_FILE = config.WIKIDATA_MAPPINGS + "name_to_qid.txt"
MID_TO_QID_FILE = config.WIKIDATA_MAPPINGS + "mid_to_qid_combined.tsv"
QID_TO_CATEGORIES_FILE = config.WIKIDATA_MAPPINGS + "qid_to_categories_v9.txt"
QID_TO_LABEL_FILE = config.WIKIDATA_MAPPINGS + "qid_to_label_all.txt"

name_to_qid = dict()
mid_to_qid = dict()
qid_to_category = dict()
qid_to_label = dict()


def read_files():
    logger.info("Reading %s file..." % QID_TO_CATEGORIES_FILE)
    with open(QID_TO_CATEGORIES_FILE, "r", encoding="utf8") as file:
        for line in file:
            line = line.strip()
            qid, primary, secondary = line.split("\t")
            qid_to_category[qid] = (primary, secondary)

    logger.info("Reading %s file..." % QID_TO_LABEL_FILE)
    with open(QID_TO_LABEL_FILE, "r", encoding="utf8") as file:
        for line in file:
            line = line.strip()
            qid, label = line.split("\t")
            qid_to_label[qid] = label


def convert(line):
    # Skip article title and empty lines
    if line == "\n" or re.match(r"\*\*\*\*\*.*\*\*\*\*\*", line) or re.match(r"\[\[.*\]\]", line):
        return ""

    new_line = line
    for m in re.finditer(Entity.UNANNOTATED_ENTITY_PATTERN, line):
        qid_string = m.group(1)
        # "|" in original words will cause problems since it is used as separator in entity tags
        original = m.group(2).replace("|", " ")
        qid_end_idx = qid_string.find(";")
        qid = qid_string[:qid_end_idx]
        category = "unknown"
        if qid in qid_to_category:
            primary, secondary = qid_to_category[qid]
            primary = primary.strip(":").replace(":", "_").replace(" ", "_")
            secondary = secondary.strip(":").replace(":", "_").replace(" ", "_")
            category = primary + "/" + secondary
            if primary == secondary and secondary == "unknown":
                category = "unknown"
        label = ""
        if qid in qid_to_label:
            label = qid_to_label[qid]
        name = qid + ":" + label
        repl_str = "[" + name + "|" + category + "|" + original + "]"
        new_line = new_line.replace(m.group(0), repl_str)

    return new_line


def main(args):
    read_files()
    logger.info("Convert entities in %s to category format." % args.input_file)
    output_file = open(args.output_file, "w", encoding="utf8")
    with open(args.input_file, "r", encoding="utf8") as file:
        for line in file:
            new_line = convert(line)
            output_file.write(new_line)
    logger.info("Done. Output written to %s" % args.output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input_file", type=str, required=True,
                        help="FQ File containing filtered questions")

    parser.add_argument("-o", "--output_file", type=str, required=True,
                        help="Output file")

    main(parser.parse_args())

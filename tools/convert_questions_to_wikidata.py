"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Convert Freebase entity mentions in input questions to Wikidata.
Or add Wikidata label and category for entities of the format [Q123||<original>].
"""

import logging
import re
import time
import config
import argparse
import os
import sys
import inspect

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from entity import Entity

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
    logger.info("Reading %s file..." % NAME_TO_QID_FILE)
    with open(NAME_TO_QID_FILE, "r", encoding="utf8") as file:
        for line in file:
            line = line.strip()
            name, qid = line.split("\t")
            name_to_qid[name] = qid

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

    logger.info("Reading %s file..." % MID_TO_QID_FILE)
    with open(MID_TO_QID_FILE, "r", encoding="utf8") as file:
        for line in file:
            line = line.strip()
            lst = line.split("\t")
            if len(lst) != 2:
                logger.info("Weird line: %s" % line)
                continue
            mid, qid = lst
            mid_to_qid[mid] = qid


def convert(question):
    new_q = question
    counter = 0
    for m in re.finditer(Entity.ANNOTATED_ENTITY_PATTERN, question):
        ent = Entity(m.group(1), m.group(2), m.group(3))
        if ent.clean_name() in name_to_qid and name_to_qid[ent.clean_name()] in qid_to_category:
            # Some qids were filtered out in qid_to_categories.txt because they
            # are wikimedia entiites. Therefore above check is necessary
            qid = name_to_qid[ent.clean_name()]
            primary, secondary = qid_to_category[qid]
            primary = primary.strip(":").replace(":", "_").replace(" ", "_")
            secondary = secondary.strip(":").replace(":", "_").replace(" ", "_")
            label = qid_to_label[qid]
            category = primary + "/" + secondary
            if primary == secondary and secondary == "unknown":
                category = "unknown"
            name = qid + ":" + label
            repl_str = "[" + name + "|" + category + "|" + ent.original + "]"
        elif ent.category in ["Year", "Month"]:
            # These are not real FB entities, but handmade entities
            # They appear only in answers which don't play a role in QAC
            continue
        else:
            # 686524 entities could not be converted to wikidata in fq_2019-03-08.hteo-tdet
            # affecting 676271 questions
            counter += 1
            repl_str = "[" + ent.clean_name() + "|unknown|" + ent.original + "]"
        new_q = new_q.replace(m.group(0), repl_str)
    return new_q, counter


def convert_cw(question):
    new_q = question
    counter = 0
    for m in re.finditer(r"\[(m\..*?)\|(.*?)\]", question):
        mid = m.group(1)
        orig_word = m.group(2)
        if mid in mid_to_qid and mid_to_qid[mid] in qid_to_category:
            # Some qids were filtered out in qid_to_categories.txt because they
            # are wikimedia entiites. Therefore above check is necessary
            qid = mid_to_qid[mid]
            primary, secondary = qid_to_category[qid]
            primary = primary.strip(":").replace(":", "_").replace(" ", "_")
            secondary = secondary.strip(":").replace(":", "_").replace(" ", "_")
            label = qid_to_label[qid]
            category = primary + "/" + secondary
            if primary == secondary and secondary == "unknown":
                category = "unknown"
            name = qid + ":" + label
            repl_str = "[" + name + "|" + category + "|" + orig_word + "]"
        else:
            # 262039 entities could not be converted to wikidata in questions_cw.txt
            counter += 1
            repl_str = "[unknown|unknown|" + orig_word + "]"
        new_q = new_q.replace(m.group(0), repl_str)
    return new_q, counter


def annotate_wd(question):
    new_q = question
    counter = 0
    for m in re.finditer(Entity.ANNOTATED_ENTITY_PATTERN, question):
        ent = Entity(m.group(1), m.group(2), m.group(3))
        if ":" in ent.name:
            qid = ent.name.split(":")[0]
        elif re.match(r"[qQ][0-9]+", ent.name):
            qid = ent.name.upper()
        else:
            logger.warning("Weird entity name: \"%s\". Skip." % ent.name)
            counter += 1
            continue
        if qid not in qid_to_category:
            category = "unknown"
        else:
            primary, secondary = qid_to_category[qid]
            primary = primary.strip(":").replace(":", "_").replace(" ", "_")
            secondary = secondary.strip(":").replace(":", "_").replace(" ", "_")
            category = primary + "/" + secondary
            if primary == secondary and secondary == "unknown":
                category = "unknown"
        label = qid_to_label.get(qid, "")
        name = qid + ":" + label
        repl_str = "[" + name + "|" + category + "|" + ent.original + "]"
        new_q = new_q.replace(m.group(0), repl_str)
    return new_q, counter


def main(args):
    read_files()
    logger.info("Convert input question entities from freebase to wikidata:")
    start = time.time()
    num_questions = 0
    no_mapping_counter = 0
    out_file = open(args.output_file, "w", encoding="latin-1")
    with open(args.fq_file, "r", encoding="latin-1") as file:
        for line in file:
            line = line
            if args.clueweb:
                question, counter = convert_cw(line)
            elif args.annotate_wd:
                question, counter = annotate_wd(line)
            else:
                question, counter = convert(line)

            no_mapping_counter += counter
            out_file.write(question.encode("latin-1", "ignore").decode("latin-1"))

            num_questions += 1

            if num_questions % 1000000 == 0:
                t = (time.time() - start) / 60
                logger.info("Converted %d questions in %f minutes." % (num_questions, t))

    logger.info("Read EOF. Converted %d questions in %f seconds" % (num_questions, time.time() - start))
    logger.info("%d entities could not be converted to wikidata." % no_mapping_counter)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--question_file", type=str, required=True,
                        help="FQ File containing filtered questions")

    parser.add_argument("--output_file", type=str, required=True,
                        help="Output file")

    parser.add_argument("--clueweb", default=False, action="store_true",
                        help="Input questions are cluewebb questions")

    parser.add_argument("--annotate_wd", default=False, action="store_true",
                        help="Only add label and category for entities of the format [Q123||<original>]")

    main(parser.parse_args())

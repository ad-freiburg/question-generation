"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Replace entity mentions in the input questions by their type.
Clean question by removing unwanted tokens.
"""

import re
import time
import logging
import argparse
from nltk.tokenize import RegexpTokenizer
from nltk.corpus import stopwords
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

stop = set(stopwords.words('english'))
tok = r"""[^!"#$%&()+.:;<=>@^\`{|}~“”\s]+"""


def clean_question(line, exclude_stopwords, tokenizer=RegexpTokenizer(tok)):
    # filters out above tokens.
    question = tokenizer.tokenize(line.lower())
    if exclude_stopwords:
        question = [w for w in question if w not in stop]

    return ' '.join(question)


def adjust_type(typ):
    if typ == "" or typ == "unknown" or typ == "unknown/unknown":
        logger.debug("no type.")
        typ = "unknown"
    typ = typ.replace(" ", "_")
    typ = typ.replace("(", "*")
    typ = typ.replace(")", "*")
    return typ


def process_questions(line, q_col, separator, exclude_unknown, replace):
    line = line.strip()
    cols = line.split(separator)
    if q_col >= len(cols):
        logger.error("Question column %d out of bound %d" % (q_col, len(cols)))
        return
    q = cols[q_col]

    # Make sure the trailing question mark is separated by whitespace
    q = re.sub(r"([^ ])\?$", r"\1 ?", q)

    # Put the entities in the question into the correct format
    for m in re.finditer(Entity.ANNOTATED_ENTITY_PATTERN, q):
        ent = Entity(m.group(1), m.group(2), m.group(3))
        typ = ent.category
        if exclude_unknown and (typ == "" or typ == "unknown"):
            return ""
        if replace and typ == "Type/domain equivalent topic":
            # Replace entities with this category by the undisambiguated
            # lowercase entity name (e.g. song, mountain, color)
            ent.name = ent.remove_disambiguation().lower()
            replacement = ent.clean_name()
        else:
            typ = adjust_type(typ)
            replacement = "[" + typ + "]"
        q = q.replace(m.group(0), replacement, 1)

    return q


def main(args):
    if args.debug:
        logger.setLevel(logging.DEBUG)

    exclude_unknown = args.exclude_unknown
    exclude_stopwords = args.exclude_stopwords
    replace = args.replace

    logger.info("Process input questions:")
    start = time.time()
    num_questions = 0
    while True:
        try:
            line = input("")

            if line == "quit":
                exit()

            processed_question = process_questions(line, args.question_column, args.separator, exclude_unknown, replace)
            question = clean_question(processed_question, exclude_stopwords)
            if question:
                print(question)

            num_questions += 1

            if num_questions % 1000000 == 0:
                t = (time.time() - start) / 60
                logger.info("Processed %d questions in %f minutes." %
                            (num_questions, t))

        except EOFError:
            logger.info("Read EOF. Processed %d questions in %f seconds" %
                        (num_questions, time.time() - start))
            exit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")

    parser.add_argument("-q_col", "--question_column", type=int, default=1,
                        help="Column of the question in the input file, 0-based")

    parser.add_argument("--separator", type=str, default="\t",
                        help="Column separator")

    parser.add_argument("--replace", default=False, action="store_true",
                        help="Replace type 'type/domain equivalent topic' by entity name.")

    parser.add_argument("--exclude_unknown", default=False, action="store_true",
                        help="Exclude questions that contain entities of an unknown type.")

    parser.add_argument("--exclude_stopwords", default=False, action="store_true",
                        help="Exclude stopwords in questions.")

    main(parser.parse_args())

"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Given a aligned file with the original source sentence containing entities,
transfer entity mentions to the input questions.
"""

import argparse
import logging
import time
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


def insert_entity_mentions(string, entities):
    entities.sort(key=lambda x: len(x.original), reverse=True)
    for ent in entities:
        # If string is a question with a whitespace before "?" this line is enough
        if ent.category in ["Month", "Year"]:
            continue
        string = string.replace(" " + ent.original.lower() + " ", " " + ent.to_entity_format() + " ")
        """
        string = string.replace(" " + ent.original.lower() + "\n", " " + ent.to_entity_format() + "\n")
        string = string.replace(" " + ent.original.lower() + "\t", " " + ent.to_entity_format() + "\t)
        string = string.replace("\t" + ent.original.lower() + " ", "\t" + ent.to_entity_format() + " ")
        string = string.replace("\t" + ent.original.lower() + "\n", "\t" + ent.to_entity_format() + "\n")
        string = string.replace("\t" + ent.original.lower() + "\t", "\t" + ent.to_entity_format() + "\t)
        """
    return string


def main(args):
    if args.debug:
        logger.setLevel(logging.DEBUG)

    logger.info("Process input questions:")
    entity_file = open(args.entity_file, "r", encoding="latin1")
    start = time.time()
    num_questions = 0
    while True:
        try:
            line = input("")
            entity_line = entity_file.readline()

            entities = Entity.get_entities(entity_line)
            entity_mention_line = insert_entity_mentions(line, entities)
            print(entity_mention_line)

            num_questions += 1

            if num_questions % 1000000 == 0:
                t = (time.time() - start) / 60
                logger.info("Processed %d questions in %f minutes." % (num_questions, t))

        except EOFError:
            logger.info("Read EOF. Processed %d questions in %f seconds" % (num_questions, time.time() - start))
            exit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")

    parser.add_argument("--entity_file", type=str, required=True,
                        help="Output file")

    main(parser.parse_args())

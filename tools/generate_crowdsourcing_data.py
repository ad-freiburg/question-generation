"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Transform given questions, source sentence and answer to tsv file that can be
used as CrowdFlower data.
Entities are replaced by original word or entity name.
"""

import argparse
import logging
import time
import re
from random import choices, seed
import os
import sys
import inspect

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from entity import Entity

seed(1662)

population = [1, 2, 3, 4, 5]
weights = [3841, 3427, 2980, 2472, 1628]
normalizer = sum(weights)
weights = [w / normalizer for w in weights]

logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)


LINE_NUM_MAPPING = "/nfs/students/natalie-prange/qg_files/parses/entityparse_line_number_mapping.txt"


def needs_ending_dot(sent):
    return len(sent) > 0 and sent[-1] not in '.,;:!?"’\''


def read_paragraphs_from_file(input_file, max_lines):
    logger.info("Reading paragraphs from file %s" % input_file)
    paragraphs = []
    line_paragraph_mapping = []
    with open(input_file, "r", encoding="latin1") as file:
        paragraph = []
        curr_paragraph_len = choices(population, weights)[0]
        sent_offset = 0
        for i, line in enumerate(file):
            line = line.strip()
            if len(paragraph) == curr_paragraph_len or i >= max_lines:
                curr_paragraph_len = choices(population, weights)[0]
                paragraphs.append(paragraph)
                paragraph = []
                sent_offset = 0
            if i >= max_lines:
                break
            if needs_ending_dot(line.strip()):
                line += " ."
            # Strip whitespaces, remove anything in parenthesis (except for parenthesis in entities)
            # line = re.sub(r"\s\(\s[^)]*\s\)\s", " ", line)
            # Replace numbers of the format "9 100 102" with "9,100,102" as done for qg
            line = re.sub(r"(\d+)\s(?=\d+)", r"\1,", line)
            paragraph.append(line)
            line_paragraph_mapping.append((len(paragraphs), sent_offset))
            sent_offset += 1
        # Append remainder
        if len(paragraph) > 0:
            paragraphs.append(paragraph)
    return paragraphs, line_paragraph_mapping


def read_line_mapping(input_file, max_lines):
    logger.info("Reading line mapping file %s" % input_file)
    line_mapping = dict()
    with open(input_file, "r", encoding="latin1") as file:
        for i, line in enumerate(file):
            if i >= max_lines:
                break
            q_num, real_num = line.strip().split()
            q_num = int(q_num)
            real_num = int(real_num)
            if q_num not in line_mapping:
                line_mapping[q_num] = real_num
    return line_mapping


def get_paragraph_fixed(paragraphs, line_paragraph_mapping, line_mapping, line_num, correct_line_nums):
    # Line indices start with 1
    if correct_line_nums:
        real_line_num = line_num - 1
    else:
        real_line_num = line_mapping[line_num] - 1
    if real_line_num < 0:
        return None
    para_idx, _ = line_paragraph_mapping[real_line_num]
    return paragraphs[para_idx]


def replace_entity_mentions(text, regard_entity_name):
    new_text = text
    for ent in Entity.get_entities(text):
        if regard_entity_name:
            new_text = new_text.replace(ent.to_entity_format(), ent.plain_name())
        else:
            new_text = new_text.replace(ent.to_entity_format(), ent.original)
    return new_text


def clean_text(text):
    text = text.replace(" 's", "'s")
    text = text.replace(" 't", "'t")
    text = text.replace(" ?", "?")
    text = text.replace(" .", ".")
    text = text.replace(" ,", ",")
    text = text.replace(" ;", ";")
    return text


def main(args):
    q_col = args.question_column
    a_col = args.answer_column
    s_col = args.source_column
    l_col = args.line_num_column

    if len({q_col, a_col, s_col, l_col}) != 4:
        logger.error("question-, answer- and context-column must be distinct.")
        exit(1)

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.paragraph_file:
        paragraphs, line_paragraph_mapping = read_paragraphs_from_file(args.paragraph_file, args.max_lines)
        line_mapping = read_line_mapping(LINE_NUM_MAPPING, args.max_lines)

    sentence_count = 0
    start = time.time()
    logger.info("Ready for input.")
    while True:
        try:
            line = input("")
            lst = line.split(args.separator)

            if len(lst) - 1 < max(q_col, a_col, s_col, l_col):
                logger.error("column index out of bounds: %d > %d" % (max(q_col, a_col, s_col, l_col), len(lst)))
                exit(1)

            question = lst[q_col]
            answer = lst[a_col]
            source_sent = lst[s_col]
            line_num = lst[l_col]

            question_entity_free = replace_entity_mentions(question, args.regard_entity_name)
            question_entity_free = clean_text(question_entity_free)
            if question_entity_free[0].islower():
                question_entity_free = question_entity_free[0].upper() + question_entity_free[1:]

            answer_entity_free = replace_entity_mentions(answer, args.regard_entity_name)
            answer_entity_free = clean_text(answer_entity_free)
            source_sent_entity_free = replace_entity_mentions(source_sent, False)
            source_sent_entity_free = clean_text(source_sent_entity_free)

            paragraph = ""
            if args.paragraph_file:
                line_num = int(line_num)
                paragraph = get_paragraph_fixed(paragraphs, line_paragraph_mapping, line_mapping, line_num,
                                                args.correct_line_nums)
                if not paragraph:
                    continue

                for i in range(len(paragraph)):
                    paragraph[i] = replace_entity_mentions(paragraph[i], False)
                    paragraph[i] = clean_text(paragraph[i])

                paragraph = ' '.join(paragraph)

            context = paragraph if args.paragraph_file else source_sent_entity_free
            print("%s\t%s\t%s\t%s\t%s" % (line_num, question_entity_free, answer_entity_free, context, args.method))

            sentence_count += 1
            if sentence_count % 1000000 == 0:
                t = (time.time() - start) / 60
                logger.info("Processed %d questions in %f minutes.." % (sentence_count, t))

        except EOFError:
            logger.info("Read EOF. Processed %d questions in %f seconds" % (sentence_count, time.time() - start))
            exit()


if __name__ == "__main__":
    # Handle command line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")

    parser.add_argument("--method", type=str, required=True,
                        help="Replace entities by their name instead of the original word.")

    parser.add_argument("-q_col", "--question_column", type=int, default=1,
                        help="Column of the question in the input file")

    parser.add_argument("-a_col", "--answer_column", type=int, default=2,
                        help="column of the answer in the input file")

    parser.add_argument("-s_col", "--source_column", type=int, default=3,
                        help="Column of the context in the input file")

    parser.add_argument("-l_col", "--line_num_column", type=int, default=0,
                        help="Column of the line number in the input file")

    parser.add_argument("--separator", type=str, default="\t",
                        help="Column separator")

    parser.add_argument("--paragraph_file", type=str, default=None,
                        help="If a paragraph file is given, include an entire paragraph as context")

    parser.add_argument("--max_lines", type=int, default=6000000,
                        help="Maximum number of source sentences covered in the input questions")

    parser.add_argument("--correct_line_nums", default=False, action="store_true",
                        help="Line numbers in question file correspond to line numbers in paragraph file")

    parser.add_argument("-ren", "--regard_entity_name", default=False, action="store_true",
                        help="Replace entities by their name instead of the original word.")

    main(parser.parse_args())

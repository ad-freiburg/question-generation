"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Transform given questions, source sentence and answer to SQuAD format.
Create random-sized paragraphs for the source sentences.
"""

import argparse
import logging
import time
import json
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


def read_paragraphs_from_file(input_file, max_lines=1000000):
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


def read_paragraph_file(input_file, max_lines=1000000):
    logger.info("Reading paragraph file %s" % input_file)
    all_lines = []
    with open(input_file, "r", encoding="utf8") as file:
        for i, line in enumerate(file):
            line = line.strip()
            if i >= max_lines:
                break
            if needs_ending_dot(line):
                line += " ."
            all_lines.append(line)
    return all_lines


def read_line_mapping(input_file, max_lines=2000000):
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
        return None, None
    para_idx, sent_offset = line_paragraph_mapping[real_line_num]
    return paragraphs[para_idx], sent_offset


def get_paragraph_window(all_lines, line_mapping, line_num, before, after, correct_line_nums):
    # Line indices start with 1
    if correct_line_nums:
        real_line_num = line_num - 1
    else:
        real_line_num = line_mapping[line_num] - 1
    if real_line_num < 0:
        return None, None
    start_index = max(0, real_line_num - before)
    end_index = min(len(all_lines), real_line_num + after + 1)
    return all_lines[start_index:end_index], real_line_num - start_index


def get_answer_start(answer, context):
    answer_start = context.find(answer)
    if answer_start != -1:
        return answer_start

    context = context.lower()
    answer = answer.lower()
    answer_start = context.find(answer)
    if answer_start != -1:
        logger.debug("Found answer at %d by lowercasing.\nAnswer: \"%s\"\nContext: \"%s\""
                     % (answer_start, answer, context))
        return answer_start

    removed_chars = 0
    new_context = context
    new_answer = answer.replace(", ", "")
    while True:
        newer_context = new_context.replace(", ", "", 1)
        removed_chars += 2
        if newer_context == new_context:
            break

        new_context = newer_context
        answer_start = new_context.find(new_answer)

        if answer_start != -1:
            answer_start += removed_chars
            answer_start -= context[answer_start:answer_start+len(answer)].count(", ") * 2
            logger.debug("Found answer at %d by comma replacement.\nAnswer: \"%s\"\nContext: \"%s\""
                         % (answer_start, answer, context))
            return answer_start

    """ QG-Heilman
    if re.search(r"(\S)'s ", answer) and not re.search(r"(\S)'s ", context):
        answer = re.sub(r"(\S)'s ", r"\1 's", answer)
        answer_start = context.find(answer)
        return answer_start

    return -1
    """
    for i in range(1, len(answer) - 1):
        answer_start = context.find(answer[:-i])
        if answer_start != -1:
            logger.debug("Found answer at %d by searching for answer[:-%d].\nAnswer: \"%s\"\nContext: \"%s\""
                         % (i, answer_start, answer, context))
            return answer_start

    return answer_start


def replace_entity_mentions(text):
    new_text = text
    for ent in Entity.get_entities(text):
        new_text = new_text.replace(ent.to_entity_format(), ent.original)
    return new_text


def main(args):
    q_col = args.question_column
    a_col = args.answer_column
    s_col = args.source_column

    if len({q_col, a_col, s_col}) != 3:
        logger.error("question-, answer- and context-column must be distinct.")
        exit(1)

    if args.debug:
        logger.setLevel(logging.DEBUG)

    if args.paragraph_file:
        # all_lines = read_paragraph_file(args.paragraph_file, args.max_lines)
        paragraphs, line_paragraph_mapping = read_paragraphs_from_file(args.paragraph_file, args.max_lines)
        line_mapping = read_line_mapping(LINE_NUM_MAPPING, args.max_lines)

    print('{"data": [{"title": "X", "paragraphs": [', end="")
    sentence_count = 0
    prev_context = ""
    start = time.time()
    logger.info("Ready for input.")
    while True:
        try:
            line = input("")
            lst = line.split(args.separator)

            if len(lst) - 1 < max(q_col, a_col, s_col):
                logger.error("column index out of bounds: %d > %d" % (max(q_col, a_col, s_col), len(lst)))
                exit(1)

            question = lst[q_col]
            answer = lst[a_col]
            source_sent = lst[s_col]

            answer_offset = 0
            paragraph = ""

            new_question = replace_entity_mentions(question)
            new_answer = replace_entity_mentions(answer)
            new_source_sent = replace_entity_mentions(source_sent)

            if args.paragraph_file:
                line_num = int(lst[args.line_num_column])
                # paragraph, sent_idx = get_paragraph_window(all_lines, line_mapping, line_num,
                #                                            args.paragraph_before, args.paragraph_after,
                #                                            args.correct_line_nums)
                paragraph, sent_idx = get_paragraph_fixed(paragraphs, line_paragraph_mapping, line_mapping,
                                                          line_num, args.correct_line_nums)
                if not paragraph:
                    continue
                for i in range(len(paragraph)):
                    paragraph[i] = replace_entity_mentions(paragraph[i])
                new_source_sent = paragraph[sent_idx]  # the two are not identical due to dependency parse tokenizing
                answer_offset = sum([len(sent) + 1 for sent in paragraph[:sent_idx]])
                paragraph = ' '.join(paragraph)

            answer_start = get_answer_start(new_answer, new_source_sent)
            """QG-Heilman
            if new_source_sent[answer_start].isupper() and new_answer[0].islower():
                new_answer = new_answer[0].upper() + new_answer[1:]
            if re.search(r"(\S)'s ", new_answer) \
                    and not re.search(r"(\S)'s ", new_source_sent[answer_start:answer_start+len(new_answer)]):
                new_answer = re.sub(r"(\S)'s ", r"\1 's", new_answer)
            """
            if answer_start == -1:
                logger.info("Could not find answer \"%s\" in source sentence \"%s\"" % (new_answer, new_source_sent))
                if args.skip_problematic_lines:
                    continue
                else:
                    # This is to avoid mismatches between the original and the json file.
                    answer_start = 0
            answer_start = answer_start + answer_offset

            context = paragraph if args.paragraph_file else new_source_sent

            if sentence_count != 0:
                if prev_context != context:
                    print(']}', end="")
                print(',', end="")
                if args.linebreaks:
                    print()

            if prev_context != context:
                print('{"context": ' + json.dumps(context) + ', "qas": [', end="")
            answer = answer if args.keep_answer_entity else new_answer
            print('{"answers": ', end="")
            print('[{"answer_start": ' + str(answer_start) + ', "text": ' + json.dumps(answer) + '}], ', end="")
            print('"id": "' + str(sentence_count) + '", ', end="")
            print('"question": ' + json.dumps(new_question) + '}', end="")

            prev_context = context
            sentence_count += 1
            if sentence_count % 1000000 == 0:
                t = (time.time() - start) / 60
                logger.info("Processed %d questions in %f minutes.." % (sentence_count, t))

        except EOFError:
            print(']}]}]}')
            logger.info("Read EOF. Processed %d questions in %f seconds" % (sentence_count, time.time() - start))
            exit()


if __name__ == "__main__":
    # Handle command line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")

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

    parser.add_argument("--linebreaks", default=False, action="store_true",
                        help="Add line breaks to the output string to improve readability")

    parser.add_argument("--paragraph_file", type=str, default=None,
                        help="If a paragraph file is given, include an entire paragraph as context")

    parser.add_argument("-B", "--paragraph_before", type=int, default=2,
                        help="Number of lines that form paragraph before target sentence")

    parser.add_argument("-A", "--paragraph_after", type=int, default=1,
                        help="Number of lines that form paragraph after target sentence")

    parser.add_argument("--max_lines", type=int, default=6000000,
                        help="Maximum number of source sentences covered in the input questions")

    parser.add_argument("--correct_line_nums", default=False, action="store_true",
                        help="Line numbers in question file correspond to line numbers in paragraph file")

    parser.add_argument("--skip_problematic_lines", default=False, action="store_true",
                        help="Keep lines where an answer could not be found.")

    parser.add_argument("--keep_answer_entity", default=False, action="store_true",
                        help="Keep entities in the answer.")

    main(parser.parse_args())

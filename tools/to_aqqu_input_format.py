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
import os
import sys
import inspect
import json

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from entity import Entity
import config

logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

NAME_TO_MID_FILE = config.FREEBASE_MAPPINGS + "name_to_mid.txt"
MONTH_MAP = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6, "July": 7, "August": 8,
             "September": 9, "October": 10, "November": 11, "December": 12}


def read_name_to_mid_file():
    name_to_mid = dict()
    logger.info("Reading %s file..." % NAME_TO_MID_FILE)
    with open(NAME_TO_MID_FILE, "r", encoding="utf8") as file:
        for line in file:
            line = line.strip()
            name, mid = line.split("\t")
            mid = mid.replace("/", ".")
            name_to_mid[name] = mid
    return name_to_mid


def replace_entity_mentions(text, regard_entity_name):
    new_text = text
    for ent in Entity.get_entities(text):
        if regard_entity_name:
            new_text = new_text.replace(ent.to_entity_format(), ent.plain_name())
        else:
            new_text = new_text.replace(ent.to_entity_format(), ent.original)
    return new_text


def get_raw_question(text):
    text = text.replace(" 's", "'s")
    text = text.replace(" 't", "'t")
    text = text.replace(" ?", "?")
    text = text.replace(" .", ".")
    text = text.replace(" ,", ",")
    text = text.replace(" ;", ";")
    return text


def get_processed_question(text):
    text = re.sub(r"(\S)'s", r"\1 's", text)
    text = re.sub(r"(\S)'t", r"\1 't", text)
    text = re.sub(r"(\S)\?", r"\1 ?", text)
    text = re.sub(r"(\S)\.", r"\1 .", text)
    text = re.sub(r"(\S),", r"\1 ,", text)
    text = re.sub(r"(\S);", r"\1 ;", text)
    text = text.rstrip("?")
    text = text.strip()
    return text


def get_date(text):
    day_pattern = re.compile(r"(^|\s)([0-3]?[0-9])($|\s|th|nd|rd|st)")
    entities = Entity.get_entities(text)
    year = ""
    month = ""
    day = ""
    if entities:
        text_entity_free = text
        for ent in entities:
            # Take the first date occurrence
            if ent.category == "Month" and not month and ent.name in MONTH_MAP:
                month = str(MONTH_MAP[ent.name]).zfill(2)
            elif ent.category == "Year" and not year:
                year = ent.name
            text_entity_free = text_entity_free.replace(ent.to_entity_format(), "")
        match = re.search(day_pattern, text_entity_free)
        if match:
            day = match.group(2)
    else:
        match = re.search(r"\d\d\d\d?", text)
        if match:
            year = match.group(0)
        for m in MONTH_MAP.keys():
            if m in text:
                month = str(MONTH_MAP[m]).zfill(2)
                break
        match = re.search(day_pattern, text)
        if match:
            day = match.group(2)
    date_string = ""
    if year:
        date_string += year
        if month:
            date_string += "-" + month
            if day:
                date_string += "-" + day
    return date_string


def text2int(textnum):
    numwords = {}
    units = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
             "twelve", "thirteen", "fourteen", "fifteen","sixteen", "seventeen", "eighteen", "nineteen"]

    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

    scales = ["hundred", "thousand", "million", "billion", "trillion"]

    numwords["and"] = (1, 0)
    for idx, word in enumerate(units):    numwords[word] = (1, idx)
    for idx, word in enumerate(tens):     numwords[word] = (1, idx * 10)
    for idx, word in enumerate(scales):   numwords[word] = (10 ** (idx * 3 or 2), 0)

    current = result = 0
    no_number_found = True
    for word in re.split(r"[ -]", textnum):
        if word not in numwords:
            if current == result == 0:
                continue
            else:
                # Only take the first number occurrence
                break
        no_number_found = False
        scale, increment = numwords[word]
        current = current * scale + increment
        if scale > 100:
            result += current
            current = 0

    if no_number_found:
        return None

    return result + current


def get_number(string):
    match = re.search(r"[\d][\d,.]*", string)
    if match:
        num_string = match.group(0)
        num_string = num_string.replace(",", "")
        if '.' in num_string:
            try:
                return float(num_string)
            except ValueError:
                return None
        return int(num_string)
    else:
        num = text2int(string)
        return num


def main(args):
    q_col = args.question_column
    a_col = args.answer_column

    if len({q_col, a_col}) != 2:
        logger.error("question- and answer-column must be distinct.")
        exit(1)

    if args.debug:
        logger.setLevel(logging.DEBUG)

    name_to_mid = read_name_to_mid_file()

    sentence_count = 0
    dates_count = 0
    discarded_dates_count = 0
    numbers_count = 0
    discarded_numbers_count = 0
    entities_count = 0
    discarded_entities_count = 0

    start = time.time()
    logger.info("Ready for input.")
    json_obj = dict()
    json_obj["Questions"] = list()
    while True:
        try:
            line = input("")
            lst = line.split(args.separator)

            if len(lst) - 1 < max(q_col, a_col):
                logger.error("column index out of bounds: %d > %d" % (max(q_col, a_col), len(lst)))
                exit(1)

            question = lst[q_col]
            answer = lst[a_col]

            question_entity_free = replace_entity_mentions(question, args.regard_entity_name)
            raw_question = get_raw_question(question_entity_free.lower())
            processed_question = get_processed_question(question_entity_free.lower())

            question_dict = dict()
            question_dict["QuestionsId"] = sentence_count
            question_dict["RawQuestion"] = raw_question
            question_dict["ProcessedQuestion"] = processed_question
            question_dict["Parses"] = list()

            parses_dict = dict()
            parses_dict["ParseId"] = str(sentence_count) + ".P0"
            # Add keys whose value is not needed but which need to be to prevent a key error
            parses_dict["Sparql"] = None
            parses_dict["InferentialChain"] = None
            parses_dict["TopicEntityMid"] = None
            parses_dict["Constraints"] = None
            parses_dict["Answers"] = list()

            answer_entities = Entity.get_entities(answer)
            answer_categories = [e.category for e in answer_entities]
            answer_names = {e.name for e in answer_entities}
            date = False
            number = False
            answers_dict = dict()
            if answer_names.intersection(MONTH_MAP.keys()) \
                    or "Year" in answer_categories or "when" == question.split(" ")[0].lower():
                dates_count += 1
                date_string = get_date(answer)
                if not date_string:
                    logger.debug("Discarded date: %s\t%s" % (question, answer))
                    discarded_dates_count += 1
                    continue
                answers_dict["AnswerArgument"] = date_string
                answers_dict["AnswerType"] = "Value"
                answers_dict["EntityName"] = None
                parses_dict["Answers"].append(answers_dict)
                date = True
            elif "how" == question.split(" ")[0].lower():
                numbers_count += 1
                number_string = get_number(answer)
                if not number_string:
                    discarded_numbers_count += 1
                    continue
                answers_dict["AnswerArgument"] = number_string
                answers_dict["AnswerType"] = "Value"
                answers_dict["EntityName"] = None
                parses_dict["Answers"].append(answers_dict)
                number = True
            else:
                entities_count += 1
                for ent in answer_entities:
                    answers_dict = dict()
                    if ent.name in name_to_mid:
                        answers_dict["AnswerType"] = "Entity"
                        answers_dict["AnswerArgument"] = name_to_mid[ent.name]
                        answers_dict["EntityName"] = ent.name
                        parses_dict["Answers"].append(answers_dict)

            if not answers_dict:
                discarded_entities_count += 1
                continue

            # Entity answers will be discarded more often due to missing name to mid mapping. However, the ratio
            # between entity answers and number/date answers should not be changed by this to-aqqu-format-formatting
            if dates_count and entities_count and numbers_count:
                if date and discarded_dates_count / dates_count < discarded_entities_count / entities_count:
                    discarded_dates_count += 1
                    continue
                if number and discarded_numbers_count / numbers_count < discarded_entities_count / entities_count:
                    discarded_numbers_count += 1
                    continue

            question_dict["Parses"].append(parses_dict)
            json_obj["Questions"].append(question_dict)

            sentence_count += 1
            if sentence_count % 1000000 == 0:
                t = (time.time() - start) / 60
                logger.info("Processed %d questions in %f minutes.." % (sentence_count, t))

        except EOFError:
            logger.info("%f" % (discarded_dates_count / dates_count))
            logger.info("%f" % (discarded_numbers_count / numbers_count))
            logger.info("%f" % (discarded_entities_count / entities_count))
            print(json.dumps(json_obj, indent=2))
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

    parser.add_argument("--separator", type=str, default="\t",
                        help="Column separator")

    parser.add_argument("-ren", "--regard_entity_name", default=False, action="store_true",
                        help="Replace entities by their name instead of the original word.")

    main(parser.parse_args())

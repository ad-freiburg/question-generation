"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Count number of questions, paragraphs and articles in the input SQuAD format
json file.
"""


import json
import argparse


def count_questions(input_file):
    with open(input_file, "r", encoding="latin1") as f:
        source = json.load(f)
        question_count = 0
        paragraph_count = 0
        for article in source["data"]:
            for para in article["paragraphs"]:
                paragraph_count += 1
                for _ in para["qas"]:
                    question_count += 1
        return question_count, paragraph_count, len(source["data"])


def main(args):
    question_count, paragraph_count, article_count = count_questions(args.input_file)
    print("Number of questions: %d\nNumber of paragraphs: %d\nNumber of articles: %d"
          % (question_count, paragraph_count, article_count))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-in", "--input_file", type=str, required=True,
                        help="Input json file")

    main(parser.parse_args())

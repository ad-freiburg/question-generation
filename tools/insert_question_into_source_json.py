"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Insert generated NQG-Zhao questions into the source json file containing
context, original question and answer.
"""

import argparse
import json
from collections import OrderedDict


def main(args):
    outfile = open(args.output_file, "w", encoding="latin1")
    question_file = open(args.gq_file, "r", encoding="latin1")
    with open(args.source_file, "r", encoding="latin1") as f:
        source = json.load(f, object_pairs_hook=OrderedDict)
        for i in range(len(source["data"])):
            for j in range(len(source["data"][i]["paragraphs"])):
                for k in range(len(source["data"][i]["paragraphs"][j]["qas"])):
                    question = question_file.readline().strip()
                    source["data"][i]["paragraphs"][j]["qas"][k]["question"] = question
        json.dump(source, outfile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-src", "--source_file", type=str, required=True,
                        help="Source json file")

    parser.add_argument("-gq", "--gq_file", type=str, required=True,
                        help="Generated question file")

    parser.add_argument("-out", "--output_file", type=str, required=True,
                        help="Output file for random samples")

    main(parser.parse_args())

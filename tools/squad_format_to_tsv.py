"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Transform SQuAD format file to tsv file with columns
id, paragraph, question, answer
"""

import json
import argparse
from collections import OrderedDict


def to_tsv(input_file, output_file):
    outfile = open(output_file, "w", encoding="utf8")
    with open(input_file, "r", encoding="utf8") as f:
        source = json.load(f, object_pairs_hook=OrderedDict)
        for para in source["data"][0]["paragraphs"]:
            context = para["context"]
            context = context.replace("\n", "")
            for qas in para["qas"]:
                q_id = qas["id"]
                question = qas["question"]
                # Take the first of several possible answers
                answer = qas["answers"][0]["text"]
                outfile.write("%s\t%s\t%s\t%s\n" % (q_id, question, answer, context))


def main(args):
    to_tsv(args.input_file, args.output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-in", "--input_file", type=str, required=True,
                        help="Input json file")

    parser.add_argument("-out", "--output_file", type=str, required=True,
                        help="Output file")

    main(parser.parse_args())

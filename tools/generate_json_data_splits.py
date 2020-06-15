"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Generate a random subset of the json file in SQuAD/Aqqu format.
Or split the json file into three subsets: train, dev and test of given size.
"""

import json
from collections import OrderedDict
import random
import copy
import logging
import argparse

logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

random.seed(1662)


def get_random_samples_aqqu(input_file, output_file, sample_size, single_line):
    indent = None if single_line else 2
    output_file = open(output_file, "w", encoding="latin1")
    random_subset = dict({"Questions": []})
    with open(input_file, "r", encoding="latin1") as f:
        source = json.load(f, object_pairs_hook=OrderedDict)
        random_subset["Questions"] = random.sample(source["Questions"], min(sample_size, len(source["Questions"])))
        logger.info("Number of questions: %d" % (len(random_subset["Questions"])))
        json.dump(random_subset, output_file, indent=indent)


def get_random_samples(input_file, output_file, sample_size, single_line):
    indent = None if single_line else 2
    output_file = open(output_file, "w", encoding="latin1")
    random_subset = dict({"data": [{"title": "X"}]})
    sized_random_subset = dict({"data": [{"title": "X", "paragraphs": []}]})
    curr_size = 0
    with open(input_file, "r", encoding="latin1") as f:
        source = json.load(f, object_pairs_hook=OrderedDict)
        random_subset["data"][0]["paragraphs"] = random.sample(source["data"][0]["paragraphs"],
                                                               min(sample_size, len(source["data"][0]["paragraphs"])))
        for para in random_subset["data"][0]["paragraphs"]:
            if curr_size + len(para["qas"]) < sample_size:
                sized_random_subset["data"][0]["paragraphs"].append(para)
                curr_size += len(para["qas"])
            else:
                i = 0
                while curr_size + len(para["qas"]) > sample_size:
                    del para["qas"][i]
                    i += 1
                sized_random_subset["data"][0]["paragraphs"].append(para)
                break
        question_count = 0
        for para in sized_random_subset["data"][0]["paragraphs"]:
            for _ in para["qas"]:
                question_count += 1
        logger.info("Number of questions: %d. Number of contexts: %d"
                    % (question_count, len(sized_random_subset["data"][0]["paragraphs"])))
        json.dump(sized_random_subset, output_file, indent=indent)


def get_data_splits_aqqu(input_file, output_prefix, split_sizes, single_line):
    indent = None if single_line else 2
    files = [output_prefix + "_train.json",
             output_prefix + "_dev.json",
             output_prefix + "_test.json"]
    with open(input_file, "r", encoding="latin1") as f:
        source = json.load(f, object_pairs_hook=OrderedDict)
        for i in range(len(files)):
            subset = dict()
            prev_size = sum(split_sizes[:i])
            logger.debug("Array range: %d-%d" % (prev_size, prev_size + split_sizes[i]))
            subset["Questions"] = source["Questions"][prev_size:prev_size + split_sizes[i]]
            logger.info("Number of questions: %d" % (len(subset["Questions"])))
            json.dump(subset, open(files[i], "w", encoding="latin1"), indent=indent)
            logger.info("Generated file %s" % files[i])


def get_data_splits(input_file, output_prefix, split_sizes, single_line):
    indent = None if single_line else 2
    files = [output_prefix + "_train.json",
             output_prefix + "_dev.json",
             output_prefix + "_test.json"]
    subsets = [dict({"data": [{"title": "X", "paragraphs": []}]}) for _ in files]
    with open(input_file, "r", encoding="latin1") as f:
        current_idx = 0
        source = json.load(f, object_pairs_hook=OrderedDict)
        curr_size = 0
        for article in source["data"]:
            for para in article["paragraphs"]:
                if curr_size + len(para["qas"]) < split_sizes[current_idx]:
                    subsets[current_idx]["data"][0]["paragraphs"].append(para)
                    curr_size += len(para["qas"])
                else:
                    remainder_para = copy.deepcopy(para)
                    remainder_para["qas"] = []
                    while curr_size + len(para["qas"]) > split_sizes[current_idx]:
                        remainder_para["qas"].append(para["qas"][-1])
                        del para["qas"][-1]
                    subsets[current_idx]["data"][0]["paragraphs"].append(para)
                    curr_size = 0
                    current_idx += 1
                    if current_idx >= len(files):
                        break
                    # TODO: This can cause discrepancies when the size is smaller than the remainder para
                    subsets[current_idx]["data"][0]["paragraphs"].append(remainder_para)
                    curr_size += len(remainder_para["qas"])

    for i in range(len(files)):
        question_count = 0
        for para in subsets[i]["data"][0]["paragraphs"]:
            for _ in para["qas"]:
                question_count += 1
        logger.info("Number of questions: %d. Number of contexts: %d"
                    % (question_count, len(subsets[i]["data"][0]["paragraphs"])))
        json.dump(subsets[i], open(files[i], "w", encoding="latin1"), indent=indent)
        logger.info("Generated file %s" % files[i])


def main(args):
    if args.get_splits:
        sizes = [args.train_size, args.dev_size, args.test_size]
        if args.aqqu_format:
            get_data_splits_aqqu(args.input_file, args.output_prefix, sizes, args.single_line)
        else:
            get_data_splits(args.input_file, args.output_prefix, sizes, args.single_line)
    else:
        if args.aqqu_format:
            get_random_samples_aqqu(args.input_file, args.output_file, args.num_samples, args.single_line)
        else:
            get_random_samples(args.input_file, args.output_file, args.num_samples, args.single_line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-in", "--input_file", type=str, required=True,
                        help="Input json file")

    parser.add_argument("-out", "--output_file", type=str, default=None,
                        help="Output file for random samples")

    parser.add_argument("-n", "--num_samples", type=int, default=100000,
                        help="Number of random samples")

    parser.add_argument("--get_splits", default=False, action="store_true",
                        help="If true, get data splits from file rather than random samples")

    parser.add_argument("--output_prefix", type=str, default="data_split",
                        help="Prefix of the output file for the data splits")

    parser.add_argument("--train_size", type=int, default=80000,
                        help="Number of train samples")

    parser.add_argument("--dev_size", type=int, default=10000,
                        help="Number of dev samples")

    parser.add_argument("--test_size", type=int, default=10000,
                        help="Number of test samples")

    parser.add_argument("-aqqu", "--aqqu-format", default=False, action="store_true",
                        help="Input json is in Aqqu format.")

    parser.add_argument("--single-line", default=False, action="store_true",
                        help="Instead of pretty-printing put result into a single line.")

    main(parser.parse_args())

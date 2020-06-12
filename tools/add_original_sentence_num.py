"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Add line number in the original sentence/paragraph file as first column to
generated question file.
"""


import argparse
import logging
import time

logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)


def read_source_file(source_file, max_lines):
    logger.info("Reading paragraph file %s" % source_file)
    source_sents_map = dict()
    with open(source_file, "r", encoding="utf8") as file:
        for i, line in enumerate(file):
            line = line.strip()
            if i >= max_lines:
                break
            if line in source_sents_map:
                logger.info("Source sentence exists multiple times: %s" % line)
            source_sents_map[line] = i + 1
    return source_sents_map


def main(args):
    s_col = args.source_column

    if args.debug:
        logger.setLevel(logging.DEBUG)

    source_sents_map = read_source_file(args.source_file, args.max_lines)

    sentence_count = 0
    start = time.time()
    logger.info("Ready for input.")
    while True:
        try:
            line = input("")
            lst = line.split(args.separator)

            if len(lst) - 1 < s_col:
                logger.error("column index out of bounds: %d > %d" % (s_col, len(lst)))
                exit(1)
            lst[-1] = lst[-1].strip()

            source_sent = lst[s_col]
            if source_sent in source_sents_map:
                sent_num = source_sents_map[source_sent]
            else:
                logger.info("Sentence not found in source sentences: %s" % source_sent)
                sent_num = -1

            print("%d\t%s" % (sent_num, line.strip()))

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

    parser.add_argument("-s", "--source_column", type=int, default=1,
                        help="Column of the source sentence in the input file")

    parser.add_argument("--separator", type=str, default="\t",
                        help="Column separator")

    parser.add_argument("--source_file", type=str, required=True,
                        help="The source sentence file")

    parser.add_argument("--max_lines", type=int, default=2000000,
                        help="Maximum number of source sentences covered in the input questions")

    main(parser.parse_args())

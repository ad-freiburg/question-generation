"""
Copyright 2020, University of Freiburg
Author: Natalie Prange <prange@cs.uni-freiburg.de>

Get mapping between source sentence file and line numbers in generated questions.
(They differ since the dependency parse discards some lines.)
"""
import re
import time
import logging
import spacy
import en_core_web_md
import os
import sys
import inspect
import argparse

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from utils import clean_sentence

# Set up the logger
logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_LENGTH = 150


def sentence_segmenter(string):
    return 0, len(string)


def set_sent_starts(doc, nlp):
    """Manually set the sentence starts at the beginning of the line.

    Otherwise spaCy does an additional sentence segmentation on top of that.

    Args:
        nlp: spacy model
        doc (spacy.tokens.Doc): the document

    Returns
        spacy.tokens.Doc: document with manually set sentence starts
    """
    sent_start_char, sent_end_char = sentence_segmenter(doc.text)
    sent = doc.char_span(sent_start_char, sent_end_char)

    if not sent:
        logger.warning("Empty document")
        if len(doc) > 0:
            nlp.tagger(doc)
            nlp.parser(doc)
            # doc[0].is_sent_start = True
            return doc
        else:
            logger.info("Return none")
            return None

    sent[0].sent_start = True
    for token in sent[1:]:
        token.sent_start = False
    return doc


def create_tokenizer(nlp):
    """Custom tokenizer for SpaCy tokenization.
    The difference is that infixes are only spaces, e.g. hyphens are always
    kept such that e.g. twenty-one is treated as single word.
    """
    prefix_re = spacy.util.compile_prefix_regex(nlp.Defaults.prefixes)
    suffix_re = spacy.util.compile_suffix_regex(nlp.Defaults.suffixes)
    infix_re = re.compile(" ")
    tokenizer = spacy.tokenizer.Tokenizer(nlp.vocab,
                                          nlp.Defaults.tokenizer_exceptions,
                                          prefix_re.search,
                                          suffix_re.search,
                                          infix_re.finditer,
                                          token_match=None)
    return tokenizer


class SpacyParser:
    def __init__(self):
        logger.info("Loading model...")
        self.nlp = en_core_web_md.load()
        self.nlp.tokenizer = create_tokenizer(self.nlp)
        logger.info("Ready.")

    def parse_line(self, line):
        """Parses a given line. Line might be split into several sentences
        due to SpaCy sentence tokenization.
        Returns the parsed sentence in conll-6 (entity-format) and a boolean
        indicating whether any lines were skipped due to errors.

        Arguments:
        line - a String.
        """
        logger.debug("%s" % line)
        sent, entities = clean_sentence(line, use_singleword_originals=True)

        # Prevent SpacyParser from running out of memory
        length = len(sent.split())
        if length > MAX_LENGTH:
            logger.debug("Skipping line with %d tokens" % length)
            return True

        # Parse the sentence
        try:
            doc = self.nlp.tokenizer(sent)
        except AssertionError:
            logger.debug("Skipping line due to AssertionError: %s" % sent)
            return True

        doc = set_sent_starts(doc, self.nlp)

        # Bring the sentence into conll_6 format
        return self.entity_assignment(doc, entities)

    def entity_assignment(self, doc, entities):
        """Puts a SpaCy-parse into conll-6 format.
        The columns are for id, word, tag, head-id, relation, entity in that
        order. Returns the conll-string as well as a boolean indicating whether
        any errors occured.

        Arguments:
        doc - the parsed SpaCy doc
        entities - a list of entities as returned by clean_sentence()
        """
        if not doc:
            return 0
        entity_by_address = dict([(e.address, e) for e in entities])
        num_tokens = 0
        num_sents = 0

        for sent in doc.sents:
            num_sents += 1
            for i, word in enumerate(sent):
                # Count the number of tokens over all detected sentences
                num_tokens += 1

                # Assign entities. Make sure they are correctly assigned across
                # sentences by using num_tokens as index
                if num_tokens in entity_by_address:
                    entity = entity_by_address[num_tokens]
                    if str(word) != entity.parseable_name() \
                            and str(word) != entity.original:
                        logger.debug("Entity assignment went wrong. Entity: %s, Word: %s\n\tIn sentence: %s"
                                     % (entity.parseable_name(), word, doc))
                        return 0

        return num_sents


def main(args):
    if args.debug:
        logger.setLevel(logging.DEBUG)

    p = SpacyParser()

    num_lines = 0
    num_parses = 0
    num_errors = 0
    start = time.time()

    while True:
        try:
            line = input("")

            if line == "quit":
                exit()

            """
            error = p.parse_line(line)

            if error:
                num_errors += 1
            else:
                num_lines += 1
            print("%d\t%d" % (num_lines, num_lines+num_errors))
            """

            num_sents = p.parse_line(line)
            if num_sents == 0:
                num_errors += 1
                # TODO: only for comparison
                print("%d\t%d" % (num_parses, num_lines + num_errors))
            else:
                num_lines += 1
            for i in range(num_sents):
                print("%d\t%d" % (num_parses + i + 1, num_lines + num_errors))
            num_parses += num_sents

            if num_lines % 100000 == 0:
                t = (time.time() - start) / 60
                logger.info("%d lines parsed in %f minutes." % (num_lines, t))

        except EOFError:
            t = (time.time() - start) / 60
            logger.info("Read EOF. Parsed %d lines in %f seconds." % (num_lines, t))
            logger.info("Number of sentences skipped due to errors: %d" % num_errors)
            exit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")

    main(parser.parse_args())

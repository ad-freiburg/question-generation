# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prange@informatik.uni-freiburg.de>

import re
import time
import argparse
import logging
import spacy
import en_core_web_md

from utils import clean_sentence

# Set up the logger
logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_LENGTH = 150


def sentence_segmenter(string):
    return 0, len(string)


def set_sent_starts(doc):
    """Manually set the sentence starts at the beginning of the line.

    Otherwise spaCy does an additional sentence segmentation on top of that.

    Args:
        doc (spacy.tokens.Doc): the document

    Returns
        spacy.tokens.Doc: document with manually set sentence starts
    """
    sent_start_char, sent_end_char = sentence_segmenter(doc.text)
    sent = doc.char_span(sent_start_char, sent_end_char)

    if not sent:
        logger.warning("Empty document.")
        return doc

    sent[0].sent_start = True
    for token in sent[1:]:
        token.sent_start = False
    return doc


def to_conll_6(doc, entities):
    """Puts a SpaCy-parse into CoNLL-6 (CoNLL-entity) format.

    The columns are for id, word, tag, head-id, relation, entity in that
    order.

    Args:
        doc (spacy.tokens.Doc): the parsed SpaCy doc
        entities (list): a list of entities as returned by clean_sentence()

    Returns:
        str: the dependency parse string in CoNLL-6 format / None if an error
            occurred
    """
    entity_by_address = dict([(e.address, e) for e in entities])

    num_sents = 0
    num_tokens = 0
    dep_string = ""

    for sent in doc.sents:
        num_sents += 1

        # Make sure multiple detected sentences are at least properly
        # separated by newline
        if num_sents > 1:
            dep_string += "\n"

        for i, word in enumerate(sent):
            # Count the number of tokens over all detected sentences
            num_tokens += 1

            # Get the head id
            if word.head is word:
                head_idx = 0
            else:
                # The head id is the head id of the word - the index of the
                # first word of the sentence + 1
                head_idx = word.head.i - sent[0].i + 1

            # Root node should be labeled "root" instead of "ROOT" to
            # ensure backwards compatibility with already parsed dataset
            dep = word.dep_
            if word.dep_ == "ROOT":
                dep = "root"

            # Assign entities. Make sure they are correctly assigned across
            # sentences by using num_tokens as index
            entity = None
            if num_tokens in entity_by_address:
                entity = entity_by_address[num_tokens]
                if str(word) != entity.parseable_name() and str(word) != entity.original:
                    logger.debug("Entity assignment went wrong. Entity: %s, Word: %s\n\tIn sentence: %s"
                                 % (entity.parseable_name(), word, doc))
                    return
                entity = entity_by_address[num_tokens]

            # Put the word into conll_6 format
            dep_string += ("%d\t%s\t%s\t%d\t%s\t%s\n" % (i+1, word, word.tag_, head_idx, dep, entity))

    if num_sents > 1:
        logger.debug("More than one sentence: %s" % [str(sent) for sent in doc.sents])

    return dep_string


class SpacyParser:
    def __init__(self, spacy_sent_tokenizer=False):
        logger.info("Initializing spaCy parser...")
        self.spacy_sent_tokenizer = spacy_sent_tokenizer
        self.nlp = en_core_web_md.load()
        self.init_tokenizer()

    def init_tokenizer(self):
        """Initializes a custom tokenizer for SpaCy tokenization.

        The difference is that infixes are only spaces, e.g. hyphens are always
        kept such that e.g. twenty-one is treated as single word.
        """
        prefix_re = spacy.util.compile_prefix_regex(self.nlp.Defaults.prefixes)
        suffix_re = spacy.util.compile_suffix_regex(self.nlp.Defaults.suffixes)
        infix_re = re.compile(" ")
        tokenizer = spacy.tokenizer.Tokenizer(self.nlp.vocab,
                                              self.nlp.Defaults.tokenizer_exceptions,
                                              prefix_re.search,
                                              suffix_re.search,
                                              infix_re.finditer,
                                              token_match=None)
        self.nlp.tokenizer = tokenizer

    def parse_line(self, line):
        """Parses a given line.

        Line might be split into several sentences due to SpaCy sentence
        tokenization.

        Args:
            line (str): input sentence

        Returns:
            str: the dependency parse string in CoNLL-6 format / None if an
                error occurred
        """
        logger.debug("%s" % line)
        sent, entities = clean_sentence(line, use_singleword_originals=True, remove_article=False)

        # Prevent SpacyParser from running out of memory
        length = len(sent.split())
        if length > MAX_LENGTH and not self.spacy_sent_tokenizer:
            logger.warning("Skipping line with %d tokens" % length)
            return

        # Parse the sentence
        try:
            doc = self.nlp.tokenizer(sent)
        except AssertionError:
            logger.debug("Skipping line due to AssertionError: %s" % sent)
            return

        if not self.spacy_sent_tokenizer:
            doc = set_sent_starts(doc)

        self.nlp.tagger(doc)
        self.nlp.parser(doc)

        # Bring the sentence into conll_6 format
        conll_str = to_conll_6(doc, entities)
        return conll_str


def main(args):
    if args.debug:
        logger.setLevel(logging.DEBUG)

    dep_parser = SpacyParser(spacy_sent_tokenizer=args.spacy_sent_tokenizer)
    num_lines = 0
    num_errors = 0
    start = time.time()
    logger.info("Ready for input.")
    while True:
        try:
            line = input("")
            parse_string = dep_parser.parse_line(line)
            if parse_string:
                print(parse_string)

            if parse_string is None:
                num_errors += 1
            else:
                num_lines += 1

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

    parser.add_argument("--spacy_sent_tokenizer", default=False, action="store_true",
                        help="Use the spacy sentence tokenizer instead of assuming one sentence per line.")

    main(parser.parse_args())

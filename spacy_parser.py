# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prange@informatik.uni-freiburg.de>

import re
import time
import argparse
import logging
import spacy
import en_core_web_md
from entity import Entity

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
    logger.debug("entities:")
    for e in entities:
        logger.debug("%s" % e)

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
                if str(word) != entity.parseable_name() and str(word) != entity.original \
                        and str(word) != entity.parseable_original():
                    logger.debug("Entity assignment went wrong. Entity: %s, Original: %s,  Word: %s\n\tIn sentence: %s"
                                 % (entity.parseable_name(), entity.original, word, doc))
                    return
                entity = entity_by_address[num_tokens]

            # Put the word into conll_6 format
            dep_string += ("%d\t%s\t%s\t%d\t%s\t%s\n" % (i+1, word, word.tag_, head_idx, dep, entity))

    if num_sents > 1:
        logger.debug("More than one sentence: %s" % [str(sent) for sent in doc.sents])

    return dep_string


class SpacyParser:
    def __init__(self, spacy_sent_tokenizer=False, wikidata=False):
        logger.info("Initializing spaCy parser...")
        self.spacy_sent_tokenizer = spacy_sent_tokenizer
        self.wikidata = wikidata
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

    def clean_sentence(self, sentence, use_singleword_originals=False, remove_article=False):
        """Cleans a sentence from entity annotations.

         Returns the cleaned sentence as well as a list of its entities.

         Args:
             sentence (str): the sentence
             use_singleword_originals (bool): if True, entities are replaced by
                their original word if it consists of a single token
             remove_article (bool): if True, "the" before entity mentions is
                removed in certain cases, e.g. for "the [Actrius|Film|film]"

         Returns:
            tuple: the sentence as string and the list of entities contained in it
        """
        # Strip whitespaces, remove anything in parenthesis (except for parenthesis
        # in entities)
        sentence = sentence.strip()
        sentence = re.sub(r"\s\([^)]*\)", "", sentence)

        # Replace numbers of the format "9 100 102" with "9,100,102" since
        # apparently this causes great grief to nltk's dependency graph
        sentence = re.sub(r"(\d+)\s(?=\d+)", r"\1,", sentence)

        # Find all entity occurrences of the form
        # [<entity_name>|<category>|<original_word>]
        matches = re.finditer(r"(?P<a>\b[tT]he\s)?(\[(?P<e>[^\]\[|]*?)\|" +
                              r"(?P<c>[^\]\[|]*?)\|(?P<o>[^\]\[|]*?)\])", sentence)
        entities = []
        num_old_chars = len(sentence)

        for m in matches:
            # Compute number of chars that were removed / added in the last step
            num_removed_chars = num_old_chars - len(sentence)

            if self.wikidata:
                qid, name = m.group('e').split(":", 1)
                entity = Entity(name, m.group('c'), m.group('o'), None, qid)
            else:
                entity = Entity(m.group('e'), m.group('c'), m.group('o'))

            # Remove the article before the entity name if the original word was
            # written in lowercase and an article precedes the entity.
            # Example: The [Actrius|film] was produced in 1996
            # --> Actrius was produced in 1996 .
            if remove_article and (m.group('a') is not None and entity.original
                                   and entity.original.islower()
                                   and entity.original.lower() != entity.name.lower()):
                replacement = m.group(2)
                # replacement = m.group('a') + m.group('o') + " " + m.group(2)
                sentence = sentence.replace(m.group(0), replacement, 1)
                num_removed_chars = num_removed_chars + len(m.group('a') + " ")

            if use_singleword_originals and len(entity.original.split(" ")) == 1:
                # If the original is a single word don't replace by entity name,
                # since it will be treated as one word and the parse will be more
                # reliable if e.g. "his" is not replaced by "Albert_Einstein"
                sentence = sentence.replace(m.group(2), entity.original, 1)
            elif entity.parseable_name() == "":
                sentence = sentence.replace(m.group(2), entity.parseable_original(), 1)
            else:
                # Replace all entities in the sentence by the parseable entity name
                # (since we want all of the entity treated as one word)
                sentence = sentence.replace(m.group(2), entity.parseable_name(), 1)

            # Get the address of the entity.
            # NOTE: Splitting only at spaces might not be completely reliable
            # ADJUSTED: Split at hyphens and whitespaces since spacy doesn't split
            # solely at whitespaces
            word_lst = self.nlp.tokenizer(sentence[:max(m.start(2) - num_removed_chars, 0)])
            address = len([w for w in word_lst if w]) + 1
            entity.set_address(address)
            entities.append(entity)

        return sentence, entities

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
        sent, entities = self.clean_sentence(line, use_singleword_originals=True, remove_article=False)

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

    dep_parser = SpacyParser(spacy_sent_tokenizer=args.spacy_sent_tokenizer, wikidata=args.wikidata)
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

    parser.add_argument("-wd", "--wikidata", default=False, action="store_true",
                        help="Input entities are Wikidata entities")

    main(parser.parse_args())

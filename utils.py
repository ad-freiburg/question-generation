# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prange@informatik.uni-freiburg.de>

import re
from entity import Entity


def clean_sentence(sentence, use_singleword_originals=False, regard_entity_name=False):
    """Cleans a sentence from entity annotations.

     Returns the cleaned sentence as well as a list of its entities.

     Args:
         sentence (str): the sentence
         use_singleword_originals (bool): if True, entities are replaced by
            their original word if it consists of a single token
         regard_entity_name (bool): if True, "the" before entity mentions is
            removed in certain cases, e.g. for "the [Actrius|Film|film]"

     Returns:
        tuple: the sentence as string and the list of entities contained in it
    """

    # Strip whitespaces, remove anything in parenthesis (except for parenthesis
    # in entities)
    sentence = sentence.strip()
    sentence = re.sub(r"\s\(\s[^)]*\s\)\s", " ", sentence)

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

        entity = Entity(m.group('e'), m.group('c'), m.group('o'))

        # Remove the article before the entity name if the original word was
        # written in lowercase and an article precedes the entity.
        # Example: The [Actrius|film] was produced in 1996
        # --> Actrius was produced in 1996 .
        if regard_entity_name and (m.group('a') is not None and entity.original
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
        else:
            # Replace all entities in the sentence by the parseable entity name
            # (since we want all of the entity treated as one word)
            sentence = sentence.replace(m.group(2), entity.parseable_name(), 1)

        # Get the address of the entity.
        # NOTE: Splitting only at spaces might not be completely reliable
        # ADJUSTED: Split at hyphens and whitespaces since spacy doesn't split
        # solely at whitespaces
        word_lst = sentence[:max(m.start(2) - num_removed_chars, 0)].split(" ")
        address = len([w for w in word_lst if w]) + 1
        entity.set_address(address)
        entities.append(entity)

    return sentence, entities

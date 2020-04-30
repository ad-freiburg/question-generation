# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prange@informatik.uni-freiburg.de>

import re
import logging
import copy
import time
import argparse
import config
from collections import defaultdict
from nltk.stem.wordnet import WordNetLemmatizer
from nltk.stem import SnowballStemmer
from nltk.corpus import stopwords
from entity_dependency_graph import EntityDependencyGraph
from entity import Entity
from spacy_parser import SpacyParser

# Set up the logger
logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

# Color schemes
WARNING = '\033[93m'
ENDC = '\033[0m'
BOLD = '\033[1m'

NAME_TO_TYPE_IDS_PATH = config.QG_MAPPINGS + "qg_name_to_type_ids.txt"
QG_TYPES_PATH = config.QG_MAPPINGS + "qg_types.txt"

MONTHS = {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"}
CONTEXT_WORDS = {"also", "then", "however", "instead", "therefore", "otherwise", "immediately", "later", "even"}
WHO_CATEGORIES = {"Person", "Fictional Character", "Musical Artist", "Musical Group", "Sports Team"}
PRONOUNS = {"she", "he", "it", "they"}
POSS_PRONOUNS = {"her", "his", "its", "their"}
OBJ_PRONOUNS = {"her", "him", "it", "them"}
ALL_PRONOUNS = PRONOUNS.union(POSS_PRONOUNS).union(OBJ_PRONOUNS)


def get_dependency_graph(parse_string):
    """Returns the dependency graph for a sentence given its parse string.

    Args:
        parse_string (str): the parse in ConLL-entity format

    Returns:
        EntityDependencyGraph: the dependency graph
    """
    return EntityDependencyGraph(parse_string, cell_separator="\t", top_relation_label='root')


def get_plural(word):
    """Returns the plural of a given word according to English grammar rules.

    Some rules which do not always apply are left out:
    For words ending in "f" or "fe" the plural is sometimes (but not
    always) formed with "ves". For words ending in "o" the plural is sometimes
    (but not always) formed with "oes"

    Args:
        word (str): a noun

    Returns:
        str: the word in plural form
    """
    if word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    elif word.endswith("sh") or word.endswith("ch") or word.endswith("s") or word.endswith("x"):
        return word + "es"
    elif word.endswith("z"):
        return word + "zes"
    else:
        return word + "s"


def det_aux_word(predicate, infinitive, dep_graph):
    """Determines the auxiliary word for a question given the predicate.

    Args:
        predicate (dict): the node of the predicate of the sentence
        infinitive (str): the infinitive of the predicate of the sentence
        dep_graph (EntityDependencyGraph): the dependency graph

    Returns:
        tuple: lists of auxiliary words and list of passive auxiliary words
    """
    aux = []
    auxpass = []
    for k, v in predicate['deps'].items():
        if k in ['aux', 'auxpass']:
            for el in v:
                aux_node = dep_graph.get_by_address(el)
                if aux_node:
                    if k == "aux":
                        aux.append(aux_node['word'])
                    else:
                        auxpass.append(aux_node['word'])

    if not (aux + auxpass) and infinitive != 'be':
        if predicate['tag'] in ["VBP", "VB"]:
            # Verb in base form or non-3rd person singular present form
            aux.append("do")
        elif predicate['tag'] == "VBZ":
            # Verb in 3rd person singular present form
            aux.append("does")
        elif predicate['tag'] == "VBD":
            # Verb in past tense
            aux.append("did")
        predicate['word'] = infinitive

    logger.debug("Aux: %s, auxpass: %s" % (aux, auxpass))
    return aux, auxpass


def rm_subclauses(dep_graph):
    """Removes subclauses indicated by a comma or semicolon from the sentence.

    Args:
        dep_graph (EntityDependencyGraph): the dependency graph
    """
    root = dep_graph.get_root()
    if not root:
        return

    rm_list = []
    seq_start = 1
    main_sentence = False
    main_sentence_before = False
    sorted_nodes = sorted(dep_graph.nodes.items())
    last_rel = ""
    last_rel_before_comma = ""
    addr = -1
    for addr, n in sorted_nodes:
        if n['word'] == ",":
            if main_sentence:
                seq_start = addr
                last_rel_before_comma = last_rel
            else:
                rm_list += range(seq_start, addr + 1)
                seq_start = addr + 1
            main_sentence = False
        elif n['word'] == ";":
            if main_sentence_before:
                rm_list += range(addr, sorted_nodes[-1][0] + 1)
                break
            rm_list += range(1, addr + 1)
            seq_start = addr + 1
            main_sentence = False

        if not main_sentence and (n['rel'] == root
                                  or (n['rel'] in ["nsubj", "nsubjpass", "dobj", "iobj", "prep"]
                                      and n['head'] == root['address'])
                                  or (n['rel'] == "amod"
                                      and last_rel_before_comma == "amod")):
            main_sentence = True
            main_sentence_before = True

        last_rel = n['rel']

    # Remove the last part of the sentence as well if it's not the main
    # sentence
    if not main_sentence:
        rm_list += range(seq_start, addr + 1)

    # remove nodes marked for removal and their dependent nodes
    for addr in rm_list:
        if addr in dep_graph.nodes:
            dep_graph.remove_by_address(addr)
    logger.debug("Sent after subclause-removal: %s" % dep_graph.to_sentence())


def repair_poss_pronoun_parse(dep_graph):
    """Repairs the parse for entities whose original word is "her".

    These are often tagged incorrectly as sth other than compound/nmod/poss.
    Always tag them as poss if they are with high probability not an object
    pronoun.

    NOTE: These errors in the parse mainly come from entities being replaced
    during the parse by the entity name instead of the original word. This
    problem does not exist in the current spacy_parser.py anymore.

    Args:
        dep_graph (EntityDependencyGraph): the dependency graph
    """
    for n in dep_graph.nodes.values():
        if n['entity']:
            orig = n['entity'].original.lower()
            next_n = dep_graph.get_by_address(n['address'] + 1)
            is_obj_pronoun = not next_n or not (next_n['tag'].startswith("NN") or next_n['tag'].startswith("JJ"))
            if orig == "her" and not is_obj_pronoun:
                n['rel'] = "poss"


def recover_pronouns(dep_graph):
    """Replaces certain pronoun-entities with their original word.

    Replace occurrences like
    "[A|person|A] wrote [A|person|her] first book..."
    with
    "[A|person|A] wrote her first book..."
    To get a question like "Who wrote her first book in 1992" instead of
    "Who wrote [person] first book in 1992?"

    Args:
        dep_graph (EntityDependencyGraph): the dependency graph
    """

    def is_poss_pronoun(node):
        pronouns = ["his", "its", "their"]
        poss_rels = ["compound", "nmod", "poss"]
        word = node['entity'].original.lower()
        # "her" has to be treated separately since it is not always a
        # possessive pronoun
        return word in pronouns or (word == "her" and node['rel'] in poss_rels)

    reflexives = ["himself", "herself", "themselves", "itself"]

    # Only replace entity by possessive pronoun if the entity occurs in the
    # sentence as a non-possessive pronoun as well
    ent_occ = []
    non_pron_ent_occ = []
    for n in dep_graph.nodes.values():
        e = n['entity']
        if e:
            # Recover pronouns if the entity name they refer to appeared already in the sentence
            # Always recover reflexive pronouns
            if e.original.lower() in reflexives or (is_poss_pronoun(n) and e.name in ent_occ):
                n['entity'] = None
                n['word'] = e.original.lower()
            else:
                ent_occ.append(e.name)
                if not is_poss_pronoun(n):
                    non_pron_ent_occ.append(e.name)

    # If an entity appears as non-possessive-pronoun in the question, recover all its pronoun occurrences,
    # independent of whether it occurs before or after the non-pronoun version
    for n in dep_graph.nodes.values():
        e = n['entity']
        if e:
            if is_poss_pronoun(n) and e.name in non_pron_ent_occ:
                n['entity'] = None
                n['word'] = e.original.lower()

    logger.debug("Sent after prp recovery: %s" % dep_graph.to_sentence())


def needs_poss_apostrophe_s(node):
    """Returns True iff the entity original is a possessive pronoun and
    regard_entity_name is True such that the entity needs an appended " 's".
    E.g. "[Alice|Person|her] book" -> "[Alice|Person|her] 's book"

    Args:
        node (dict): the entity node

    Returns:
        True iff the node needs an appended possessive " 's"
    """
    if not node['entity']:
        return False

    if node['entity'].original.lower() in ["his", "their", "its"] or \
            (node['entity'].original.lower() == "her" and node['rel'] in ["compound", "nmod", "poss"]):
        return True

    return False


def is_chronological_sentence(dep_graph):
    """Returns true if the sentence is a chronological sentence.

    E.g. a sentence of the form "1992 – Olympic games are held in Barcelona"
    The problem is not only that the year and hyphen appear in weird places
    within the question, but also that the questions are often in present
    tense, which usually does not make much sense.

    Args:
        dep_graph (EntityDependencyGraph): the dependency graph

    Returns:
        bool: True iff the sentence is a chronological sentence
    """
    sentence = dep_graph.to_sentence()
    if re.match(r"[0-9.,/]+\sâ\x80\x93\s", sentence):
        logger.debug("Is a chronicle sentence.")
        return True
    return False


def get_sub_list(rels, dep_graph, root_addr=None):
    """Returns the subtree of the first node matching <rels> as list of nodes.

    Args:
        rels (list): rels for which to match
        dep_graph (EntityDependencyGraph): the dependency graph
        root_addr (int): root address. If not None, only nodes whose head is
            the root are included in the subtree
            (default is None)

    Returns:
        list: subtree
    """
    nodes = [n for n in dep_graph.get_by_rel(rels)]
    for n in nodes:
        if not root_addr or n['head'] == root_addr:
            subtree = dep_graph.get_subtree(n)
            subtree.append(n)
            logger.debug("Sublist: %s" % subtree)
            return sorted(subtree, key=lambda x: x['address'])
    return []


def get_str_list_from_node_list(q_list, mask_entities=False, append_poss_s=False):
    """Retrieves a list of words from a mixed string-node list.

    Args:
        q_list (list): a list of strings and dependency nodes
        mask_entities (bool): entities are returned as "[x]" if true
            (default is False)
        append_poss_s (bool): whether to append possessive s for prp$ originals

    Returns:
        list: words in the sentence
    """
    result = []
    entity_mask = "[x]"
    for el in q_list:
        if type(el) is str:
            result.append(el)
        elif el['entity']:
            if mask_entities:
                result.append(entity_mask)
            else:
                result.append(el['entity'].to_entity_format())
            if append_poss_s and needs_poss_apostrophe_s(el):
                result.append("'s")
        else:
            result.append(el['word'])
    return result


def remove_time_phrase(dep_graph):
    """Removes pobj time phrases in the dependency graph.

    E.g. "in 1997"

    Args:
        dep_graph (EntityDependencyGraph): the dependency graph

    Returns:
        None
    """
    for _, n in sorted(dep_graph.nodes.items()):
        if n['rel'] == 'pobj':
            # The word is an object of a preposition (pobj) and the preposition is the head
            head = dep_graph.nodes[n['head']]

            if (re.match(r"\d\d\d\d", n['word']) or n['word'] in MONTHS) and head['tag'] == "IN":
                # Don't form a question if the preposition is e.g. "for", "since" or "to"
                allowed_preps = ["in", "at", "on", "by", "after", "before", "from"]
                if head['word'].lower() in allowed_preps:
                    dep_graph.rm_deps_recursively(head)
                    dep_graph.remove_by_address(head["address"])
                    logger.debug("Removed time phrase. new sentence: %s" % dep_graph.to_sentence())


class QuestionGenerator:
    """A class for generating questions from sentences with entity mentions.

    Entity mentions are in the format [<entity_name>|<category>|<original word>]
    """

    def __init__(self, parse_input, regard_entity_name):
        if parse_input:
            self.spacy_parser = SpacyParser()
        self.lemmatizer = WordNetLemmatizer()
        self.stemmer = SnowballStemmer('english')
        self.name_to_type_ids = defaultdict(list)
        self.id_to_type = list()
        self.stopwords = set(stopwords.words('english'))
        self.read_name_to_types()
        self.regard_entity_name = regard_entity_name

    def read_name_to_types(self):
        """Read name-to-type ids and id-to-type mappings.

        Returns:
            None
        """
        logger.info("Reading name_to_types dictionary...")
        with open(NAME_TO_TYPE_IDS_PATH, "r", encoding="utf8") as file:
            for line in file:
                lst = line.split("\t")
                lst[-1] = lst[-1].strip()
                ids = [int(i) for i in lst[1:]]
                self.name_to_type_ids[lst[0]] = ids

        logger.info("Reading type_to_id dictionary...")
        with open(QG_TYPES_PATH, "r", encoding="utf8") as file:
            for line in file:
                typ = line.strip()
                self.id_to_type.append(typ)

    def det_wh_word(self, entity, q_list, root, answer_rel):
        """Determines the wh-word by which an answer entity will be replaced.

        Args:
            entity (Entity): answer entity
            q_list (list): list of words and nodes that form the question
            root (node): root node of the sentence
            answer_rel (string): rel of the answer node

        Returns:
            list: list of wh-words
        """
        if answer_rel == 'nummod':
            wh_words = ['How many']
        elif entity.category in WHO_CATEGORIES:
            if answer_rel == 'poss':
                wh_words = ['Whose']
            else:
                wh_words = ["Who"]
        else:
            wh_words = []

            # Add "Which <type>" question words
            if entity.name in self.name_to_type_ids:
                tok_lem_sentence = get_str_list_from_node_list(q_list, mask_entities=True)
                tok_lem_sentence = [self.lemmatizer.lemmatize(t.lower()) for t in tok_lem_sentence]
                type_ids = self.name_to_type_ids[entity.name]
                # Only form a which <type> question if <type> does not already exist in the sentence
                # To avoid sth like "Which country is the 4th largest country in Africa?"
                types = [self.id_to_type[i] for i in type_ids]
                types = [t for t in types if self.lemmatizer.lemmatize(t.lower()) not in tok_lem_sentence]
                # Avoid sth like "Which city is a village in ..."
                if "City/Town/Village" in types:
                    types.remove("City/Town/Village")
                    if self.lemmatizer.lemmatize("village") not in tok_lem_sentence \
                            and self.lemmatizer.lemmatize("town") not in tok_lem_sentence \
                            and self.lemmatizer.lemmatize("city") not in tok_lem_sentence:
                        types.append("City")
                        types.append("Town")

                # Append plural 's' to the type if the root is a present
                # non-3rd person singular verb and the question is a subject
                # question (otherwise I can't tell from the root if the
                # answer entity is plural)
                if answer_rel in ['nsubj', 'nsubjpass']:
                    if root['tag'] == "VBP":
                        for i, typ in enumerate(types):
                            if " of " in typ.lower():
                                idx = typ.lower().index(" of ")
                                types[i] = get_plural(typ[:idx]) + typ[idx:]
                            else:
                                types[i] = get_plural(typ)

                appendix = " 's" if answer_rel == 'poss' else ""
                wh_words = ["Which " + typ.lower() + appendix for typ in types]

            if answer_rel != 'poss':
                wh_words.append("What")

        logger.debug("WH-Words: %s" % wh_words)
        return wh_words

    def correct_entity_recognition(self, q_list):
        """Corrects problematic entity recognition by merging entities.

        E.g. "[Albert Einstein|Person|Albert] [Albert Einstein|Person|Einstein]"
        --> "[Albert Einstein|Person|Albert Einstein]"

        Args:
            q_list (list):  list of tokens of the question

        Returns:
            list: list of tokens in the question
        """
        e_pattern = re.compile(r"\[([^\s|\]]*?)\|([^\]\[|]*?)\|([^\]\[|]*?)\]")

        i = 0
        while i < len(q_list):
            m1 = re.match(e_pattern, q_list[i])
            if not m1:
                i += 1
                continue

            e_name = m1.group(1)
            e_word = m1.group(3)
            e_type = m1.group(2)
            if i < len(q_list) - 1:
                m2 = re.match(e_pattern, q_list[i + 1])
                # If the succeeding word is an entity, the two entity names are
                # the same, the two entity words are not the same and both
                # entity words appear in the entity name, merge the entities
                clean_e_name = e_name.lower().replace("_", " ")
                if m2 and e_name == m2.group(1) and e_word != m2.group(3) and e_word.lower() in clean_e_name \
                        and m2.group(3).lower() in clean_e_name:
                    fused_original = e_word + " " + m2.group(3)
                    new_e = Entity(e_name, e_type, fused_original)
                    q_list[i] = new_e.to_entity_format()
                    del q_list[i + 1]
                    # Need to check the same entity again in case it's an
                    # incorrectly recognized more-than-two-word entity.
                    continue
                if not m2:
                    # Avoid things like
                    # [Uni_of_Calgary|...|Uni of] [Alabama|...|Alabama]
                    succ_non_stop_list = []
                    for w in q_list[i + 1:]:
                        if w not in self.stopwords:
                            e = re.match(e_pattern, w)
                            if e:
                                succ_non_stop_list.append(e.group(3))
                            else:
                                succ_non_stop_list.append(w)
                            break
                        succ_non_stop_list.append(w)

                    succ_string = '_'.join(succ_non_stop_list)

                    # If the succeeding word is not an entity and the entity
                    # name starts with the entity word and the succeeding words
                    # up to the first non-stopword.
                    # Catch sth like [American History X|..|American History] X
                    clean_e_word = e_word.lower().replace(" ", "_")
                    str_start = clean_e_word + "_" + succ_string.lower()
                    if e_name.lower().startswith(str_start):
                        clean_succ_string = succ_string.replace("_", " ")
                        fused_original = e_word + " " + clean_succ_string
                        new_e = Entity(e_name, e_type, fused_original)
                        e_str = new_e.to_entity_format()
                        q_list[i] = e_str
                        for _ in range(len(succ_non_stop_list)):
                            del q_list[i + 1]
                        # Need to check the same entity again in case it's an
                        # incorrectly recognized more-than-two-word entity.
                        continue
            if i > 0:
                prev = q_list[i - 1]
                # If the previous word is not an entity, the previous word is
                # the first word of the entity name and the entity word the
                # second. Catch sth like: the [The Hobbit|Written_Work|Hobbit]
                str_start = prev + "_" + e_word.replace(" ", "_")
                if not re.match(e_pattern, prev) and e_name.startswith(str_start):
                    fused_original = prev + " " + e_word
                    new_e = Entity(e_name, e_type, fused_original)
                    q_list[i] = new_e.to_entity_format()
                    del q_list[i - 1]
                    # Need to check the same entity again in case it's an
                    # incorrectly recognized more-than-two-word entity.
                    i -= 1
                    continue
            i += 1

        return q_list

    def remove_entity_mentions(self, string):
        """Remove entity mentions for entities where entity recognition is
        not reliable.

        E.g. "The [World War II|Event|world]".
        Returns an empty string if missing context is likely to be introduced
        by removal of the problematic entity mentions.

        Args:
            string (str): the question or answer string

        Returns:
            str: input string with certain entity mentions removed
        """
        entities = Entity.get_entities(string)
        ent_names = [e.name for e in entities]
        for i, ent in enumerate(entities):
            stem_name = "".join([self.stemmer.stem(t) for t in ent.clean_name().lower().split(" ")])
            stem_original = "".join([self.stemmer.stem(t) for t in ent.original.lower().split(" ")])
            if ent.original.islower() and ent.original.lower() not in ALL_PRONOUNS and stem_name != stem_original:
                the_before_entity = "the " + ent.to_entity_format() in string
                the_before_entity = the_before_entity or "The " + ent.to_entity_format() in string
                other_ent_names = ent_names[:i] + ent_names[i + 1:]
                if ent.name not in other_ent_names and the_before_entity:
                    logger.debug("return empty string for %s" % string)
                    return ""
                string = string.replace(ent.to_entity_format(), ent.original)
        return string

    def form_answer(self, node, dep_graph):
        """Returns the answer node to the question in entity format.

        Creates the appropriate format for answers that are not entities
        (i.e. dates).

        Args:
            node (dict): the answer node
            dep_graph (EntityDependencyGraph): the dependency graph

        Returns:
            str: the answer
        """

        def _get_date_entity(n):
            if re.match(r"\d\d\d\d", n['word']):
                n['entity'] = Entity(n['word'], "Year", n['word'])
            elif n['word'] in MONTHS:
                n['entity'] = Entity(n['word'], "Month", n['word'])
            return n

        # Get answer entity
        date = False
        if not node['entity']:
            date = True
            node = _get_date_entity(node)

        # Get subtree from the head of the node if it's a pobj to include prepositions in the answer
        if node['rel'] == "pobj":
            node = dep_graph.get_by_address(node['head'])

        # Add answer entity dependencies to the answer
        subtree = dep_graph.get_subtree(node)
        if date:
            subtree = [_get_date_entity(s) for s in subtree]
        subtree.append(node)
        sublist = sorted(subtree, key=lambda x: x['address'])
        sublist = get_str_list_from_node_list(sublist, mask_entities=False, append_poss_s=self.regard_entity_name)
        return " ".join(sublist)

    def form_question(self, word_list, wh_words, answer):
        """Forms a question from a given list of nodes and strings.

        Args:
            word_list (list): list of nodes and strings
            wh_words (list): list of wh-words that can be used as first word(s)
            answer (str): the answer entity for the question

        Returns:
            list: list of questions
        """
        exists_entity = False
        filtered_list = []
        for i, n in enumerate(word_list):
            if type(n) == str:
                filtered_list.append(n)
                continue
            if n['rel'] == "punct":
                # Omit punctuation in the question except for commas unless
                # they appear directly before another punctuation or
                # directly after the question word and the next word is an
                # aux verb or predicate
                verbs = ["root", "aux", "auxpass"]
                if not n['word'] == ',' or word_list[i + 1] == "?" \
                        or (i == 0 and (type(word_list[i + 1]) == str or word_list[i + 1]['rel'] in verbs)) \
                        or (type(word_list[i + 1]) != str and word_list[i + 1]['rel'] == "punct"):
                    continue
            if n['word']:
                filtered_list.append(n)
            if n['entity']:
                exists_entity = True
                # Add missing possessive "s", as in:
                # "[A|Person|her] book" -> "[A|Person|her] 's book"
                # s.t. the abstract question will later be "[Person] 's book"
                if self.regard_entity_name and needs_poss_apostrophe_s(n):
                    filtered_list.append("'s")

        logger.debug("filtered_list: %s" % filtered_list)
        # Only create questions that contain at least one entity
        # and have at least three words (2 plus question word)
        if not exists_entity or len(filtered_list) <= 1:
            return []

        # Remove the second to last element (last is "?") if it's a dangling
        # hyphen or cc (and, or, ...)
        last = filtered_list[-2]
        while type(last) != str and (last['word'] in ['â\x80\x93', "-"] or last['rel'] in ['cc', 'punct']):
            del filtered_list[-2]
            if len(filtered_list) <= 1:
                return []
            last = filtered_list[-2]

        # Create the list of strings that represent the question
        q_list = []
        for i, n in enumerate(filtered_list):
            if type(n) == str:
                # Append the word if the element is a string (e.g. an aux)
                q_list.append(n)
            elif n['entity']:
                # Append entities in the correct format [<name>|<category>]
                e_string = n['entity'].to_entity_format()
                q_list.append(e_string)
            elif n['word']:
                q_list.append(n['word'])

        q_list = self.correct_entity_recognition(q_list)
        q_string = ' '.join(q_list)

        if self.regard_entity_name:
            # Remove certain possibly erroneous entity mentions
            q_string = self.remove_entity_mentions(q_string)
            answer = self.remove_entity_mentions(answer)
            if not q_string or not answer:
                return []

        questions = []
        for wh_word in wh_words:
            questions.append((wh_word + " " + q_string, answer))

        return questions

    def get_object_question(self, node, wh_words, dep_graph):
        """Generates an object question for a given node and question word.

        Args:
            node (dict): object node that will form the answer to the question
            wh_words (list): the wh-words for the question that is to be generated
            dep_graph (EntityDependencyGraph): the dependency graph

        Returns:
            list: object questions
        """
        new_graph = copy.deepcopy(dep_graph)
        node = new_graph.get_by_address(node['address'])

        # Get the answer entity/word
        answer = self.form_answer(node, new_graph)
        entity = node['entity']
        node['entity'] = None

        # Determine everything that belongs to this object and replace it by
        # the wh-word
        new_graph.rm_deps_recursively(node)
        logger.debug("Sent after deps_removal: %s" % new_graph.to_sentence())

        # Remove the preposition. Only if it's a when or where question,
        # otherwise head is not a preposition
        if node['rel'] == 'pobj':
            # If the preposition is "to", don't remove it to avoid questions
            # like "Where did [Louis_Riel|Person|Riel] and his comrades flee ?"
            head = dep_graph.nodes[node['head']]
            if head['word'] != "to":
                logger.debug("Preposition of pobj removed.")
                new_graph.remove_by_address(node['head'])

        # If it's a when-question, remove other occurrences of time phrases
        if "When" in wh_words:
            remove_time_phrase(new_graph)

        # lower original first word if it is not a proper noun or "I"
        first_node = new_graph.get_by_address(1)
        if first_node and first_node['word'] and first_node['tag'] not in ["NNP", "NNPS"] and first_node['word'] != 'I':
            first_node['word'] = first_node['word'].lower()

        # If the question is a "Where"-question don't append another pobj
        # Location
        # TODO: this introduces a lot of garbage sentences where parts are missing.
        if "Where" in wh_words:
            for n in new_graph.get_by_rel(["pobj"]):
                entity = n['entity']
                if entity is not None and entity.category == "Location":
                    if n['head'] is None:
                        continue
                    head = new_graph.get_by_address(n['head'])
                    if head is None or head['word'] in ["of", "from", "by", "with", "for", "as", "to"]:
                        continue
                    new_graph.rm_deps_recursively(head)
                    if n['head'] in new_graph.nodes:
                        new_graph.remove_by_address(n['head'])

        # Compose the question. The wh-words will be appended in the end.
        q_list = []

        if node['rel'] == 'poss':
            head = new_graph.nodes[node['head']]
            subtree = new_graph.get_subtree(head, [node['address']])
            subtree.append(head)
            q_list += sorted(subtree, key=lambda x: x['address'])
            new_graph.rm_deps_recursively(node)
            new_graph.remove_by_address(node['address'])

        # Get the infinitive of the predicate
        root = new_graph.get_root()
        if not root:
            logger.debug("No root node found: %s" % new_graph.to_sentence())
            return []
        infinitive = self.lemmatizer.lemmatize(root['word'], 'v')

        # Determine the auxiliary verb
        aux, auxpass = det_aux_word(root, infinitive, new_graph)

        # If this is the case something might have gone wrong during parsing
        if not (aux + auxpass) and infinitive != 'be':
            logger.debug("Weird root. Skip: %s" % new_graph.to_sentence())
            return []

        # Append auxiliary verb
        if infinitive != 'be':
            if aux:
                q_list += aux[:1]
            else:
                q_list += auxpass
                auxpass = []
        else:
            q_list.append(root)

        # Counteract bad entity recognition by replacing entities in sentences
        # like "[x|y|It] became clear that..." by the original word "it"
        subj_list = new_graph.get_by_rel(['nsubj', 'nsubjpass'])
        if len(subj_list) > 0:
            subj = subj_list[0]
            if subj['entity'] and subj['entity'].original.lower() == "it" and "ccomp" in root['deps'].keys():
                subj['word'] = "it"
                subj['entity'] = None

        # Append subject subtree
        subj_sub_list = get_sub_list(['nsubj', 'nsubjpass'], new_graph, root['address'])

        # Don't form a question if there is no subject dependent on the root
        if not subj_sub_list:
            return []

        # Remove leading hyphen
        if subj_sub_list[0]['word'] in ['â\x80\x93', "-"]:
            del subj_sub_list[0]

        q_list += subj_sub_list

        # Append the root and its advmod if it has one
        if infinitive != 'be':
            q_list += aux[1:]
            q_list += auxpass
            pred_list = new_graph.get_predicate_list(root)
            # Remove words that need a context before the root
            q_list += [p for p in pred_list if p['word'] not in CONTEXT_WORDS]

        # Append remaining parts
        for i, n in sorted(new_graph.nodes.items()):
            if i is None:
                continue
            if node['address'] < root['address']:
                # Append everything after the root if the target node comes
                # before the root
                if i > root['address'] and n not in q_list:
                    q_list.append(n)
            else:
                # Otherwise append everything between the root and the target
                # node's head
                if root['address'] < i < node['head'] and n not in q_list:
                    q_list.append(n)

        # Append prepositional phrase that depends on the root
        # E.g. instead of "What did [Gershwin|...|G] compose ?"
        # --> "What did [Gershwin|...|G] compose on commission
        #      from the conductor [Walter_Damrosch|...|...] ?"
        nodes = [n for n in new_graph.get_by_rel(["prep"]) if n['head'] == root['address']]
        subtree = []
        for n in nodes:
            if n in q_list or n['address'] < root['address']:
                continue

            # Don't add phrase if it contains the answer entity.
            new_subtree = new_graph.get_subtree(n)
            if node in new_subtree:
                continue

            # If the question is a where-question don't append location pobjs
            # --> avoid: "Where does [A||] have a star at [X|Location|..] ?
            #      [Hollywood_Walk_of_Fame|Location|..]"
            skip_phrase = False
            for sn in new_subtree:
                sn_ent = sn['entity']
                if sn['rel'] == 'pobj' and "Where" in wh_words and sn_ent is not None \
                        and sn_ent.category == "Location":
                    skip_phrase = True
                    break
            if skip_phrase:
                break

            subtree += new_subtree
            subtree.append(n)
            if subtree:
                # Otherwise, too much unnecessary stuff is added and the
                # question gets bulky
                break
        q_list += sorted(subtree, key=lambda x: x['address'])

        # Only append a comp sublist if it is not in the q_list already and if
        # it is not before the root node
        nodes = [n for n in new_graph.get_by_rel(["ccomp", "xcomp"]) if n['head'] == root['address']]
        subtree = []
        for n in nodes:
            if n in q_list or n['address'] < root['address']:
                continue
            subtree += new_graph.get_subtree(n)
            subtree.append(n)
        q_list += sorted(subtree, key=lambda x: x['address'])

        q_list.append("?")

        # Get wh words if question is not a where or when question
        if not wh_words:
            wh_words = self.det_wh_word(entity, q_list, root, node['rel'])

        # Plug entities back in and put question into the correct format:
        questions = self.form_question(q_list, wh_words, answer)

        return questions

    def generate_object_questions(self, root, dep_graph):
        """Generates questions from a sentence by asking for the object of that
        sentence.

        Args:
            root (dict): root node of the question
            dep_graph (EntityDependencyGraph): the dependency graph

        Returns:
            list: object questions
        """
        questions = []
        for _, n in sorted(dep_graph.nodes.items()):
            entity = n['entity']
            q = []

            # Only ask, if the object is part of the main clause.
            if not n['word'] or not dep_graph.in_main_dependencies(root, n):
                continue

            head = dep_graph.nodes[n['head']]

            if entity is not None and n['rel'] == 'dobj' and entity.category != "unknown":
                # The word is a direct object (dobj)
                # if the category is unknown the question word cannot be properly determined
                q = self.get_object_question(n, [], dep_graph)

            elif entity is not None and n['rel'] == 'poss' and head['rel'] in ['dobj']:
                q = self.get_object_question(n, [], dep_graph)

            elif n['rel'] == 'pobj':
                # The word is an object of a preposition (pobj)

                # This excludes many questions where the answer is not correct.
                # Unless this is not a problem, this can be left out.
                if head['head'] != root['address']:
                    continue

                # head of a pobj is not always a prep.
                if entity is not None and entity.category == "Location" and head['rel'] == "prep" \
                        and head['tag'] in ["IN", "RP"]:
                    # Only form question if the head preposition is not "for"
                    # to avoid sth like:
                    # "Where did [Ayn_Rand|Person|She] set out ?" --> Hollywood
                    if head['word'] not in ["for", "as", "of", "from", "by", "with"]:
                        # Check whether to form a Where-question
                        q = self.get_object_question(n, ["Where"], dep_graph)

                elif (re.match(r"\d\d\d\d", n['word']) or n['word'] in MONTHS) and head['tag'] == "IN":
                    # Don't form a question if the preposition is e.g. "for",
                    # "since" or "to"
                    allowed_preps = ["in", "at", "on", "by", "after", "before", "from"]
                    if head['word'].lower() in allowed_preps:
                        # Check whether to form a When-question
                        q = self.get_object_question(n, ["When"], dep_graph)

            elif n['rel'] == 'iobj':
                # indirect (dative) object is not covered. Rarely occurs (not
                # at all in first 100 sents)
                pass

            questions += q

        return questions

    def generate_subject_question(self, root, dep_graph):
        """Generates questions from a sentence by asking for the subject of
        that sentence.

        Forms either "What", "Which <type>" or "Who" questions.

        Args:
            root (dict): root node of the question
            dep_graph (EntityDependencyGraph): the dependency graph

        Returns:
            list: subject questions
        """
        questions = []
        for i, n in sorted(dep_graph.nodes.items()):
            entity = n['entity']

            # Only ask, if the object is part of the main clause.
            if not dep_graph.in_main_dependencies(root, n):
                continue

            # The word can either be a nominal subject or a passive nominal
            # subject
            head = dep_graph.get_by_address(n['head'])
            root = dep_graph.get_root()
            if entity is not None and ((n['rel'] in ['nsubj', 'nsubjpass'] and entity.category != "unknown") or
                                       (n['rel'] == 'poss' and head['rel'] in ['nsubj', 'nsubjpass'])) or \
                    (n['rel'] == 'nummod' and head['rel'] in ['nsubj', 'nsubjpass'] and
                     head['tag'] in ['NNS', 'NNPS'] and self.lemmatizer.lemmatize(root['word'], 'v') != 'be'):
                # Counteract bad entity recognition by excluding sentences like
                # "[x|y|It] became clear that..."
                if entity and entity.original.lower() == "it" and "ccomp" in root['deps'].keys():
                    continue

                # Do not create How-many-question if the nummod is preceeded by an article like
                # "The 1997 movie [Actirus|film|Actirus] ..."
                if n['rel'] == 'nummod':
                    dep_nodes = dep_graph.get_subtree(head)
                    skip = False
                    for dn in dep_nodes:
                        if dn['rel'] == 'det' or (dn['word'] and dn['word'].lower() in ["that", "these", "those"]):
                            skip = True
                            break
                    if skip:
                        continue

                new_graph = copy.deepcopy(dep_graph)
                n = new_graph.get_by_address(i)

                # Get the answer entity
                answer = self.form_answer(n, new_graph)
                n['entity'] = None

                # Determine everything that belongs to this subject and replace
                # it by the wh-word
                new_graph.rm_deps_recursively(n)

                # Form the new sentence and plug entities back in in the
                # correct format
                q_list = []
                min_index = n['address']
                for j, v in sorted(new_graph.nodes.items()):
                    if j is None:
                        continue
                    # Remove "also" if it appears directly before the root
                    # TODO: Consider always removing it
                    if j > min_index and (v['word'] not in CONTEXT_WORDS or (j + 1 >= len(new_graph.nodes)
                                                                             or new_graph.nodes[j + 1] != root)):
                        q_list.append(v)
                q_list.append("?")

                # Determine the correct wh-Word
                wh_words = self.det_wh_word(entity, q_list, root, n['rel'])
                if not wh_words:
                    continue

                questions += self.form_question(q_list, wh_words, answer)
        return questions

    def generate_question(self, sentence, parse_input):
        """Generates questions from a given sentence.

        Args:
            sentence (str): the sentence
            parse_input (bool): if True parse the input. Otherwise assume input is already parsed

        Returns:
            tuple: list of generated questions and the original sentence as string
        """
        # Pre-processing
        logger.debug("%s" % sentence)
        if parse_input:
            sentence = self.spacy_parser.parse_line(sentence)
            logger.debug("parse: %s" % sentence)

        if not sentence:
            return [], None

        dep_graph = get_dependency_graph(sentence)

        # Questions from sentences with a ":" are often weird
        # e.g.: "Who wrote in the [New York Times]?
        if dep_graph.has_word(":"):
            return [], None

        # If a sentence has no subject, don't generate a question
        if not dep_graph.has_subj():
            return [], None

        # Remove subclauses in the sentence
        rm_subclauses(dep_graph)

        # Replace certain named entity mentions on pronouns by the pronoun
        repair_poss_pronoun_parse(dep_graph)
        recover_pronouns(dep_graph)

        # Remove sentences of the form 1992 - The olympic games are held in BCN
        if is_chronological_sentence(dep_graph):
            return [], None

        logger.debug("Preprocessed sentence: %s" % dep_graph.to_sentence())

        # Don't create questions if there is no root or the root is not a verb
        root = dep_graph.get_root()
        if not root or root['tag'][0] != "V" or root['entity'] is not None:
            return [], None

        # Generate the questions
        original_sentence = dep_graph.to_sentence()
        questions = self.generate_subject_question(root, dep_graph)
        questions += self.generate_object_questions(root, dep_graph)
        return questions, original_sentence


def main(args):
    if args.debug:
        logger.setLevel(logging.DEBUG)

    generator = QuestionGenerator(args.parse_input, args.regard_entity_name)
    num_questions = 0
    sentence_count = 0
    start = time.time()
    logger.info("Ready for input.")
    while True:
        try:
            if not args.parse_input:
                # Read all lines up to an empty line into the string
                sentinel = ''
                line = '\n'.join(iter(input, sentinel))
            else:
                line = input("")

            sentence_count += 1
            questions, original_sent = generator.generate_question(line, args.parse_input)
            if args.parse_input:
                original_sent = line.strip("\n")
            for q in questions:
                num_questions += 1
                print("%d\t%s\t%s\t%s" % (sentence_count, q[0], q[1], original_sent))

            if sentence_count % 100000 == 0:
                t = (time.time() - start) / 60
                logger.info("Processed %d sentences." % sentence_count)
                logger.info("Generated %d questions in %f minutes." % (num_questions, t))

        except EOFError:
            logger.info("Read EOF. Generated %d questions from %d sentences in %f seconds" %
                        (num_questions, sentence_count, time.time() - start))
            exit()


if __name__ == "__main__":
    # Handle command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")
    parser.add_argument("-p", "--parse_input", default=False, action="store_true",
                        help="Parse the input. Set to true if your input is not a dependency parse")
    parser.add_argument("--regard_entity_name", default=False, action="store_true",
                        help="Set to true if the entity name should be regarded instead of the original word in the "
                             "final sentence")
    main(parser.parse_args())

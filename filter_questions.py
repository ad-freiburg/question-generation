# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prange@informatik.uni-freiburg.de>

import os
import logging
import requests
import re
import argparse
import time
import config
from entity import Entity
from collections import defaultdict
from enum import Enum
from nltk.stem import SnowballStemmer


# Set up the logger
logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)


NAME_TO_MID_PATH = config.FREEBASE_MAPPINGS + "name_to_mid.txt"
CONNECTION_PATH_FREEBASE = config.FREEBASE_MAPPINGS + "entity_connection_map.txt"
CONNECTION_PATH_WIKIDATA = config.WIKIDATA_MAPPINGS + "entity_connection_map_wd.txt"
API_HOST_FREEBASE = "http://qlever.informatik.uni-freiburg.de/api/clueweb-freebase/"
API_HOST_WIKIDATA = "http://qlever.informatik.uni-freiburg.de/api/wikidata-full/"
MAX_TOKENS = 30

PRONOUNS = {"she", "he", "it", "they"}
POSS_PRONOUNS = {"her", "his", "its", "their"}
OBJ_PRONOUNS = {"her", "him", "it", "them"}
ALL_PRONOUNS = PRONOUNS.union(POSS_PRONOUNS).union(OBJ_PRONOUNS)


def get_qlever_result(query, query_wikidata):
    """Queries the Qlever API and checks whether the result size is > 0.

    Args:
        query (str): SPARQL query
        query_wikidata (bool): whether to query Freebase or Wikidata

    Returns:
        bool: True iff the result size is > 0
    """
    host = API_HOST_WIKIDATA if query_wikidata else API_HOST_FREEBASE
    data = {"query": query, "send": 10}
    counter = 0
    while True:
        counter += 1
        try:
            r = requests.get(host, params=data)
            break
        except requests.exceptions.RequestException:
            time.sleep(1)
            if counter % 10 == 1:
                logger.warning("Trying to contact host. Trial no. %d" % counter)
    if r:
        result = r.json()
        return int(result["resultsize"]) > 0

    logger.warning("No result from host for query %s" % query)
    return False


def has_mediator_connection(ent1, ent2, query_wikidata):
    """Checks whether two entities are connected by a mediator.

    Args:
        ent1 (str): MID of the first entity
        ent2 (str): MID of the second entity
        query_wikidata: whether to form a Freebase or a Wikidata SPARQL query

    Returns:
        bool: True iff the result size is > 0
    """
    if query_wikidata:
        query = ("""PREFIX wd: <http://www.wikidata.org/entity/>
                    SELECT ?p1 ?p2 ?m WHERE {
                       wd:%s ?p1 ?m .
                       ?m ?p2 wd:%s .
                    }""" % (ent1, ent2))
    else:
        query = ("""PREFIX fb: <http://rdf.freebase.com/ns/>
                    SELECT ?p1 ?m ?p2 WHERE {
                      fb:%s ?p1 ?m .
                      ?m ?p2 fb:%s .
                      FILTER (?p2 != fb:type.type.instance) .
                    }""" % (ent1, ent2))
    res = get_qlever_result(query, query_wikidata)
    return res


def has_mediator_connection_2(ent1, ent2, query_wikidata):
    """Checks whether two entities are connected by a type 2 mediator connection.

    Args:
        ent1 (str): MID of the first entity
        ent2 (str): MID of the second entity
        query_wikidata: whether to form a Freebase or a Wikidata SPARQL query

    Returns:
        bool: True iff the result size is > 0
    """
    if query_wikidata:
        query = ("""xxx%s%s""" % (ent1, ent2))
    else:
        query = ("""PREFIX fb: <http://rdf.freebase.com/ns/>
                    SELECT ?p1 ?m ?p2 WHERE {
                      fb:%s ?p1 ?m .
                      fb:%s ?p2 ?m .
                      FILTER (?m != fb:common.topic) .
                    }""" % (ent1, ent2))
    res = get_qlever_result(query, query_wikidata)
    return res


def has_direct_connection(ent1, ent2, query_wikidata):
    """Checks whether two entities are directly connected.

    Args:
        ent1 (str): MID of the first entity
        ent2 (str): MID of the second entity
        query_wikidata: whether to form a Freebase or a Wikidata SPARQL query

    Returns:
        bool: True iff the result size is > 0
    """
    if query_wikidata:
        query = ("""PREFIX wd: <http://www.wikidata.org/entity/>
                    SELECT ?p WHERE {
                       wd:%s ?p wd:%s
                    }""" % (ent1, ent2))
    else:
        query = ("""PREFIX fb: <http://rdf.freebase.com/ns/>
                    SELECT ?p WHERE {
                      fb:%s ?p fb:%s
                    }""" % (ent1, ent2))
    res = get_qlever_result(query, query_wikidata)
    return res


def get_connection_from_qlever(ent1, ent2, query_wikidata):
    """Checks whether two entities have either a direct or a mediator connection.

    Args:
        ent1 (str): MID of the first entity
        ent2 (str): MID of the second entity
        query_wikidata: whether to form a Freebase or a Wikidata SPARQL query

    Returns:
        bool: True iff the result size is > 0
    """
    res = has_mediator_connection(ent1, ent2, query_wikidata)
    res = res or has_mediator_connection(ent2, ent1, query_wikidata)
    res = res or has_direct_connection(ent1, ent2, query_wikidata)
    res = res or has_direct_connection(ent2, ent1, query_wikidata)
    return res


def mask_entities(string, mask="[x]"):
    """Masks entities in the string with the given mask.

    Args:
        mask (str): mask
        string (str): original string

    Returns:
        str: string with masked entities
    """
    return re.sub(Entity.ANNOTATED_ENTITY_PATTERN, mask, string)


class Filter(Enum):
    """Enum for different filter types.
    """
    ERROR = 1
    ANSWER_IT = 2
    COMMA = 3
    MAX_TOKENS = 4
    MISSING_CONTEXT = 5
    UPPERCASE = 6
    ENTITY_IT = 7
    LOWERCASE = 8
    CONTAINS_ANSWER = 9
    TWO_ENTITIES = 10
    NO_CONNECTION = 11
    UNRELIABLE_NER = 12


class FilterQuestions:
    """Filters questions according to various filter criteria.
    """
    def __init__(self, wikidata_entities, regard_entity_name):
        self.stemmer = SnowballStemmer('english')
        self.name_to_mid = dict()
        if not wikidata_entities:
            self.read_name_to_mid(NAME_TO_MID_PATH)
        self.max_tokens = MAX_TOKENS
        self.connection_map = defaultdict(dict)
        self.wikidata_entities = wikidata_entities
        self.regard_entity_name = regard_entity_name
        connection_path = CONNECTION_PATH_WIKIDATA if wikidata_entities else CONNECTION_PATH_FREEBASE
        if os.path.isfile(connection_path):
            self.read_connection_map(connection_path)

    def read_name_to_mid(self, filename):
        logger.info("Reading %s..." % filename)
        with open(filename, "r", encoding="utf8") as file:
            for line in file:
                name, mid = line.strip().split("\t")
                self.name_to_mid[name] = mid.replace("/", ".")

    def read_connection_map(self, filename):
        logger.info("Reading entity connection map from file %s" % filename)
        with open(filename, "r", encoding="utf8") as file:
            for line in file:
                ent1, ent2, val = line.strip().split("\t")
                val = int(val)
                self.connection_map[ent1][ent2] = val

    def write_connection_map(self, filename):
        logger.info("Writing entity connection map to file %s ..." % filename)
        with open(filename, "w", encoding="utf8") as file:
            for ent1, ent_dict in sorted(self.connection_map.items()):
                for ent2, val in ent_dict.items():
                    file.write("%s\t%s\t%d\n" % (ent1, ent2, val))

    def update_connection_map(self, ent1, ent2, val):
        if ent1 > ent2:
            # Switch such that ent1 is always the "smaller" one
            tmp = ent1
            ent1 = ent2
            ent2 = tmp
        self.connection_map[ent1][ent2] = val

    def get_connection_from_map(self, ent1, ent2):
        if ent1 > ent2:
            # Switch such that ent1 is always the "smaller" one
            tmp = ent1
            ent1 = ent2
            ent2 = tmp
        if ent1 in self.connection_map:
            if ent2 in self.connection_map[ent1]:
                return bool(self.connection_map[ent1][ent2])  # bool(0) == False; bool(1) == True

    def has_connection(self, ent1, ent2):
        res = self.get_connection_from_map(ent1, ent2)
        if res is None:
            res = get_connection_from_qlever(ent1, ent2, self.wikidata_entities)
            self.update_connection_map(ent1, ent2, int(res))  # int(False) == 0; int(True) == 1
        return res

    def filter_missing_context(self, question, answer, entities, answer_entities):
        """Filters out questions that are likely to have a MISSING_CONTEXT
        problem.

        E.g. because they contain a single word that references a context like
        "this" or "these". Or, if regard_entity_names is false, because they
        contain a type or pronoun reference like
        "When did the [300|Film|film] screen ?", "When was [Albert|Person|he]
        born ?"

        Args:
            question (str): the original question
            answer (str): the original answer
            entities (list): entities in the question
            answer_entities (list): entities in the answer

        Returns:
            bool: True iff question is filtered out
        """
        # The tokenized question with entities masked as [x]
        tokens = mask_entities(question).split(" ")
        context_words = ["this", "there", "then", "these", "they", "he", "she"]
        for t in tokens:
            # Filter questions that contain words that refer to a context which
            # is in most cases not given in the question
            if t.lower() in context_words:
                return True

        all_entities = entities + answer_entities
        all_ent_names = [e.name if e.original.lower() not in ALL_PRONOUNS else None for e in all_entities]
        for i, ent in enumerate(all_entities):
            the_before_entity = "the " + ent.to_entity_format() in question + answer
            the_before_entity = the_before_entity or "The " + ent.to_entity_format() in question + answer
            other_ent_names = all_ent_names[:i] + all_ent_names[i+1:]
            stem_name = "".join([self.stemmer.stem(t) for t in ent.clean_name().lower().split(" ")])
            stem_original = "".join([self.stemmer.stem(t) for t in ent.original.lower().split(" ")])
            if not self.regard_entity_name and stem_original != stem_name and ent.name not in other_ent_names and \
                    ((the_before_entity and ent.original.islower()) or ent.original.lower() in ALL_PRONOUNS):
                return True
        return False

    def filter_ner(self, entities, answer_entities):
        """Filter out questions which are likely to contain entities that were
        recognized erroneously.

        Args:
            entities (list): entities in the question
            answer_entities (list): entities in the answer

        Returns:
            bool: True iff question is filtered out
        """
        all_entities = entities + answer_entities
        for ent in all_entities:
            cl_bracketless_name = re.sub(r"(_|\s)\(.*\).*", "", ent.clean_name())
            stem_name = "".join([self.stemmer.stem(t) for t in cl_bracketless_name.lower().split(" ")])
            stem_original = "".join([self.stemmer.stem(t) for t in ent.original.lower().split(" ")])
            # The person-condition is to keep common cases like "[Muammar Gaddafi|Person|Gaddafi]"
            # The location-condition is to keep common cases like "the [Britain|Location|British] army"
            # TODO: do I need the islower()?
            if not ent.original.islower() and stem_name != stem_original and \
                    (ent.category != "Person" or ent.original != cl_bracketless_name.split(" ")[-1]) and \
                    (ent.category != "Location" or len(cl_bracketless_name.split(" ")) != len(ent.original.split(" "))):
                return True
        return False

    @staticmethod
    def filter_comma(question):
        """Filters out questions with a comma.

        Args:
            question (str): the original question

        Returns:
            bool: True iff question is filtered out
        """
        if "," in mask_entities(question):
            return True
        return False

    @staticmethod
    def filter_entity_it(entities):
        """Filters out questions with entities whose original word is "it".

        This can lead to wrong sentence structure, e.g.
        "What is possible to discover errors in TAI..." [||it]

        Args:
            entities (list): entities in the question or answer

        Returns:
            bool: True iff question is filtered out
        """
        for ent in entities:
            if ent.original.lower() == "it":
                return True
        return False

    def filter_max_tokens(self, question):
        """Filters out questions with more than <max_tokens> tokens.

        Args:
            question (str): the original question

        Returns:
            bool: True iff question is filtered out
        """
        if len(mask_entities(question).split(" ")) > self.max_tokens:
            return True
        return False

    @staticmethod
    def filter_gt_two_entities(entities):
        """Filters out questions with more than two entities.

        Args:
            entities (list): entities in the question

        Returns:
            bool: True iff question is filtered out
        """
        if len(entities) > 2:
            return True
        return False

    @staticmethod
    def filter_uppercase(question):
        """Filters out questions that contain uppercase tokens.

        These are often non-recognized entities (except for sentence start).

        Args:
            question (str): the original question

        Returns:
            bool: True iff question is filtered out
        """
        tokens = mask_entities(question).split(" ")
        for i, t in enumerate(tokens):
            if not t.lower() == t and i != 0:
                return True
        return False

    def filter_contains_answer(self, entities, answer_entities):
        """Filters out questions that contain their own answer.

        Args:
            entities (list): entities in the question
            answer_entities (list): entities in the answer

        Returns:
            bool: True iff question is filtered out
        """
        for ent in entities:
            if ent.name in [ae.name for ae in answer_entities] and \
                    (ent.original not in ALL_PRONOUNS or self.regard_entity_name):
                return True
        return False

    @staticmethod
    def filter_lowercase(entities):
        """Filters out questions with entities whose original word does not
        contain uppercase letters.

        ...and is not a pronoun - often these kind of entities are erroneously
        classified as entity or are classified as a wrong entity.

        However, certain types of entities will be filtered out more often
        when applying this filter, e.g. inventions: "the telephone"

        Args:
            entities (list): entities in the question

        Returns:
            bool: True iff question is filtered out
        """
        for ent in entities:
            original = ent.original
            if original.lower() == original and original.lower() not in ALL_PRONOUNS:
                return True
        return False

    def filter_id_mapping(self, entities):
        """Filters out questions with entities which cannot be mapped to a MID
        or QID.

        Args:
            entities (list): entities in the question or answer

        Returns:
            bool: True iff question was filtered out
        """
        for ent in entities:
            ent_id = self.get_entity_identifier(ent)
            if not ent_id and ent.category not in ["Year", "Month"]:
                return True
        return False

    def filter_entity_connection(self, entities, answer_entities):
        """Filters out questions with entities without a connection in the
        knowledge base.

        Always filter out questions if an entity could not be mapped to an id
        such that the connection can not be checked.

        Args:
            entities (list): entities in the question
            answer_entities (list): entities in the answer

        Returns:
            bool: True iff question is filtered out
        """
        if self.filter_id_mapping(entities):
            return True

        # Only regard the first entity in the answer
        if self.filter_id_mapping(answer_entities):
            return True

        # Get entity identifiers (MIDs or QIDs)
        ent_ids = []
        for ent in entities + answer_entities:
            ent_id = self.get_entity_identifier(ent)
            if ent_id:
                ent_ids.append(ent_id)

        # Look for each kind of connection (mediator or direct) in each
        # direction for each entity pair. Don't require connections between
        # each pair, but at least two connections, e.g. ent1 <-m- ent2 -> ent3
        # Perform a depth first search to check if the entities form a
        # connected graph
        stack = [(ent_ids[0], 0)]
        is_connected = [False for _ in ent_ids]
        while stack:
            curr_node = stack.pop()
            is_connected[curr_node[1]] = True
            for i in range(len(ent_ids)):
                next_node = ent_ids[i], i
                if is_connected[i]:
                    continue
                if self.has_connection(curr_node[0], next_node[0]):
                    stack.append(next_node)
        # Don't filter out question if the entity graph is connected
        if all(is_connected):
            return False
        return True

    def filter(self, line):
        """Filters out questions according to various filter criteria.

        Args:
            line (str): the input line

        Returns:
            str/Filter: the line if the question passes the filter criteria.
                Otherwise the filter criteria
        """
        # Check whether the input is in the line number format
        if line.count("\t") == 1:
            question, answer = line.split("\t")
        elif line.count("\t") == 2:
            _, question, answer = line.split("\t")
        elif line.count("\t") == 3:
            _, question, answer, _ = line.split("\t")
        else:
            logger.warning("Weird question format: %d tabs found." % line.count("\t"))
            return Filter.ERROR

        answer_entities = Entity.get_entities(answer)
        entities = Entity.get_entities(question)

        if self.filter_entity_it(answer_entities):
            logger.debug("filter answer it")
            return Filter.ANSWER_IT

        if self.filter_entity_it(entities):
            logger.debug("filter question it")
            return Filter.ENTITY_IT

        # In the latest qg version, comma filtering is done while generating questions
        if False and self.filter_comma(question):
            logger.debug("filter comma")
            return Filter.COMMA

        if self.filter_contains_answer(entities, answer_entities):
            logger.debug("filter contains answer")
            return Filter.CONTAINS_ANSWER

        if self.filter_missing_context(question, answer, entities, answer_entities):
            logger.debug("filter missing context")
            return Filter.MISSING_CONTEXT

        if self.filter_max_tokens(question):
            logger.debug("filter max tokens")
            return Filter.MAX_TOKENS

        if self.regard_entity_name and self.filter_ner(entities, answer_entities):
            return Filter.UNRELIABLE_NER

        if False and self.regard_entity_name and self.filter_gt_two_entities(entities):
            logger.debug("filter > 2 entities")
            return Filter.TWO_ENTITIES

        if False and self.regard_entity_name and self.filter_uppercase(question):
            logger.debug("filter uppercase")
            return Filter.UPPERCASE

        if False and self.regard_entity_name and self.filter_lowercase(entities):
            logger.debug("filter lowercase")
            return Filter.LOWERCASE

        if False and self.regard_entity_name and self.filter_entity_connection(entities, answer_entities):
            logger.debug("filter no connection")
            return Filter.NO_CONNECTION

        return line

    def get_entity_identifier(self, ent):
        """Retrieves the identifier of the given entity.

        Args:
            ent (Entity): the entity

        Returns:
            str: the entity identifier if it has one, otherwise None
        """
        if self.wikidata_entities:
            ent_id = ent.name[:ent.name.find(":")]
        else:
            name = ent.name.replace("_", " ")
            if ent.category in ["Year", "Month"]:
                return
            if name in self.name_to_mid:
                ent_id = self.name_to_mid[name]
            else:
                logger.debug("Entity name '%s' not found in name_to_mid.txt" % ent.name)
                return
        return ent_id


def main(args):
    if args.debug:
        logger.setLevel(logging.DEBUG)

    filter_file = None
    if args.filter_file:
        filter_file = open(args.filter_file, "w", encoding="utf8")

    fq = FilterQuestions(args.wikidata, args.regard_entity_name)
    total = 0
    excluded = 0
    start = time.time()
    logger.info("Filter input questions:")
    while True:
        try:
            line = input("")

            result = fq.filter(line)

            if type(result) is str:
                print(result)
            else:
                excluded += 1
                if filter_file:
                    filter_file.write("%s\t%s\n" % (line, str(result)))

            total += 1

            if total % 100000 == 0:
                t = (time.time() - start) / 60
                logger.info("Processed %d questions in %f minutes." % (total, t))
                logger.info("Kept %d questions." % (total - excluded))

        except EOFError:
            t = (time.time() - start) / 60
            logger.info("Read EOF. Processed %d questions in %f minutes." % (total, t))
            logger.info("%d questions were filtered out, %d were kept." % (excluded, total - excluded))
            connection_path = CONNECTION_PATH_WIKIDATA if fq.wikidata_entities else CONNECTION_PATH_FREEBASE
            fq.write_connection_map(connection_path)
            if filter_file:
                filter_file.close()
            exit()


if __name__ == "__main__":
    # Handle command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")
    parser.add_argument("--wikidata", default=False, action="store_true",
                        help="Entities in input sentences are from Wikidata")
    parser.add_argument("-f", "--filter_file", default="", type=str,
                        help="File path to which filtered out questions and the corresponding filter are written")
    parser.add_argument("-ren", "--regard_entity_name", default=False, action="store_true",
                        help="Set to true if the entity name should be regarded instead of the original word in the "
                             "final sentence")
    main(parser.parse_args())

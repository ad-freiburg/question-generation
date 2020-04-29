# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prange@informatik.uni-freiburg.de>

import re
import logging
from collections import defaultdict
from nltk.parse.dependencygraph import DependencyGraph
from nltk.compat import string_types
from entity import Entity

# Set up the logger
logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)


class EntityDependencyGraph(DependencyGraph):
    """A dependency graph in which entities can be assigned to certain nodes
    """
    def __init__(self, tree_str=None, zero_based=False, cell_separator=None, top_relation_label='ROOT'):
        """Similar to DependencyGraph but with an added key-value pair: entity
        """
        self.nodes = defaultdict(lambda: {'address': None,
                                          'word': None,
                                          'lemma': None,
                                          'tag': None,
                                          'head': None,
                                          'deps': defaultdict(list),
                                          'rel': None,
                                          'entity': None,
                                          })

        self.nodes[0].update({'tag': 'TOP', 'address': 0})
        self.root = None

        if tree_str:
            self._parse(
                tree_str,
                zero_based=zero_based,
                cell_separator=cell_separator,
                top_relation_label=top_relation_label,
            )

    @staticmethod
    def _extract_cells(cells):
        for i, el in enumerate(cells):
            if el == "None":
                # Take into account that the word can be the string "None"
                if i != 1 or (i == 1 and cells[0] == "None"):
                    cells[i] = None
        address, word, tag, head, rel, entity = cells
        address = int(address) if address is not None else address
        return address, word, tag, head, rel, entity

    def _parse(self, input_, zero_based=False, cell_separator=None, top_relation_label='ROOT'):
        """Parse a sentence.

        Args:
            input_ (str): the input string
            zero_based (bool):
            cell_separator (str): the cell separator. If not provided, cells
                are split by whitespace.
            top_relation_label (str): the label by which the top relation is
                identified, for example, `ROOT`, `null` or `TOP`.
        """
        if isinstance(input_, string_types):
            input_ = (line for line in input_.split('\n'))

        lines = (ln.rstrip() for ln in input_)
        lines = (ln for ln in lines if ln)

        cell_number = None
        for index, line in enumerate(lines, start=1):
            cells = line.split(cell_separator)
            if cell_number is None:
                cell_number = len(cells)
            else:
                if cell_number != len(cells):
                    logger.warning("Weird number of cells: %s, %d" %
                                   (cells, len(cells)))
                    continue

            index, word, tag, head, rel, entity_string = EntityDependencyGraph._extract_cells(cells)

            if head == '_':
                continue

            if head is not None:
                head = int(head)
            if zero_based:
                head += 1

            if entity_string:
                pat = re.compile(r"\(\"(.*)\", \"(.*)\", \"(.*)\", (\d*)\)")
                entity_tuple = re.findall(pat, entity_string)
                name, category, original, address = entity_tuple[0]
                entity = Entity(name, category, original, int(address))
            else:
                entity = None

            # This is necessary because SpaCy in its new version lets root
            # point to itself. This can cause infinite recursions in qg.py
            if rel == top_relation_label and head != 0:
                head = 0

            self.nodes[index].update(
                {
                    'address': index,
                    'word': word,
                    'tag': tag,
                    'head': head,
                    'rel': rel,
                    'entity': entity,
                }
            )
            self.nodes[head]['deps'][rel].append(index)

        if self.nodes[0]['deps'][top_relation_label]:
            root_address = self.nodes[0]['deps'][top_relation_label][0]
            self.root = self.nodes[root_address]
            self.top_relation_label = top_relation_label
        else:
            logger.warning("The graph doesn't contain a node that depends on the root element.")

    def to_conll(self):
        """Returns the dependency graph in CoNLL-6 (CoNLL-entity) format.

        Returns:
            str: the dependency graph in CoNLL-6 format
        """

        template = '{address}\t{word}\t{tag}\t{head}\t{rel}\t{entity}\n'
        return ''.join(template.format(i=i, **node) for i, node in sorted(self.nodes.items()) if node['tag'] != 'TOP')

    def get_by_address(self, node_address):
        """Returns the node with the given address.

        But without creating a new node if it doesn't exist.

        Args:
            node_address (int): address of the node to be retrieved

        Returns:
            dict: the node
        """
        if node_address in self.nodes:
            return self.nodes[node_address]

    def get_by_rel(self, rels):
        """Returns all nodes in the graph which have the given relations.

        Args:
            rels (list): list of rels for which to search

        Returns:
            list: list of nodes
        """
        nodes = []
        for i, n in sorted(self.nodes.items()):
            if n['rel'] in rels:
                nodes.append(n)
        return nodes

    def get_root(self):
        """Returns the root node of the graph if it exists.

        Returns:
            dict: the root node
        """
        root_list = self.get_by_rel(['root'])
        if len(root_list) == 1:
            return root_list[0]
        else:
            logger.debug("Weird number of roots: %d" % len(root_list))

    def get_predicate_list(self, predicate):
        """Returns the predicate, its advmod, negation and particle ("hand over",
        "shut down") if it has one.

        Args:
            predicate (dict): the predicate node of the sentence

        Returns:
            list: list of certain predicate dependent nodes
        """
        lst = [predicate]
        for k, v in predicate['deps'].items():
            if k in ['advmod', 'neg', 'prt']:
                for el in v:
                    node = self.get_by_address(el)
                    if node and node['address'] is not None:
                        lst.append(node)
        logger.debug("Predicate list: %s" % lst)
        return sorted(lst, key=lambda x: x['address'])

    def get_subtree(self, node):
        """Returns all child-nodes of a given node in the graph as a list.

        Args:
            node (dict): the parent node of the subtree that has to be extracted

        Returns:
            list: list of child nodes
        """
        lst = []
        for k, v in node['deps'].items():
            for el in v:
                dep_node = self.nodes[el]
                if dep_node['address'] is None:
                    continue
                lst += self.get_subtree(dep_node)
                lst.append(dep_node)
        return lst

    def to_sentence(self, mask_entities=False):
        """Forms a sentence from the graph.

        Args:
            mask_entities (bool): if True, entities are masked in the sentence

        Returns:
            str: sentence represented by the graph
        """
        word_list = []
        for _, n in sorted(self.nodes.items()):
            if n['word'] is not None:
                if n['entity'] is not None:
                    if mask_entities:
                        word_list.append("[x]")
                    else:
                        e = n['entity']
                        word_list.append(e.to_entity_format())
                else:
                    word_list.append(n['word'])
        return ' '.join(word_list)

    def in_main_dependencies(self, node, dependent_node):
        """Checks if a given node is within the main-dependencies of another
        node.

        Args:
            node (dict): main node
            dependent_node (dict): dependent node

        Returns:
            bool: True iff dependent node is in the main-dependencies of node
        """
        if node == dependent_node:
            return True

        address = dependent_node['address']
        for k, v in node['deps'].items():
            if k in ['prep', 'pobj', 'dobj', 'nsubj', 'nsubjpass', 'iobj', 'poss']:
                if address in v:
                    return True
                for adr in v:
                    new_node = self.get_by_address(adr)
                    if new_node:
                        found = self.in_main_dependencies(new_node, dependent_node)
                        if found:
                            return True
        return False

    def has_word(self, word):
        """Returns True if the graph contains the specified word.

        Args:
            word (str): the word for which to check

        Returns:
            bool: True iff the graph contains word
        """
        for n in self.nodes.values():
            if n['word'] == word:
                return True
        return False

    def has_subj(self):
        """Returns true if the graph contains a subject.

        Returns:
            bool: True iff the graph contains a subject
        """
        for n in self.nodes.values():
            if n['rel'] in ['nsubj', 'nsubjpass']:
                return True
        return False

    def rm_deps_recursively(self, node):
        """Removes all dependencies of a given node in the graph.

        Args:
            node (dict): the node
        """
        if node is None:
            return
        for k, v in node['deps'].items():
            for el in v:
                self.rm_deps_recursively(self.nodes[el])
                self.remove_by_address(el)

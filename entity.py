# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prange@informatik.uni-freiburg.de>

import re


class Entity:
    """A class representing an entity
    """
    ANNOTATED_ENTITY_PATTERN = re.compile(r"\[([^\]\[|]*?)\|([^\]\[|]*?)\|([^\]\[|]*?)\]")
    UNANNOTATED_ENTITY_PATTERN = re.compile(r"\[([^\]\[|]*?)\|([^\]\[|]*?)\]")

    def __init__(self, name, category, original, address=None, id=None):
        self.name = name
        self.category = category
        self.original = original
        self.address = address
        self.id = id

    def __str__(self):
        address = self.address
        if not address:
            address = -1
        id = self.id
        if not id:
            id = None

        return '("%s", "%s", "%s", %d, "%s")' % (self.name, self.category, self.original, address, id)

    @classmethod
    def to_entity(cls, string):
        """Turns a string representing an entity to an entity

        Args:
            string (str): string representation of an entity

        Returns:
            Entity: the entity
        """
        m = re.match(cls.ANNOTATED_ENTITY_PATTERN, string)
        if m:
            return Entity(m.group(1), m.group(2), m.group(3))
        return None

    @classmethod
    def get_entities(cls, string):
        """Retrieves entities of the format [<entity_name>|<category>|<original>]
        from a given string.

        Args:
            string (str): the input string

        Returns:
            list: list of entities
        """
        entities = []
        for m in re.finditer(cls.ANNOTATED_ENTITY_PATTERN, string):
            entities.append(Entity(m.group(1), m.group(2), m.group(3)))
        return entities

    def set_address(self, address):
        self.address = address

    def clean_name(self):
        """Returns the cleaned entity name (no underscores).

        Returns:
            str: cleaned entity name
        """
        clean_name = self.name.replace("__", ": ")
        clean_name = clean_name.replace("_", " ")
        return clean_name

    def remove_disambiguation(self):
        """Returns the entity name without disambiguation (no succeeding
        parenthesis and numbering)

        Returns:
            str: entity name without disambiguation
        """
        return re.sub(r"(_|\s)\(.*\).*", "", self.name)

    def plain_name(self):
        """Returns the entity name without disambiguation and without
        underscores.

        Returns:
            str: plain entity name
        """
        plain_name = re.sub(r"(_|\s)\(.*\).*", "", self.name)
        plain_name = plain_name.replace("__", ": ")
        plain_name = plain_name.replace("_", " ")
        return plain_name

    def parseable_name(self):
        """Returns the parseable name of the entity, e.g. the name in such a way
        that it will not be separated by the parser but treated as single word.

        Returns:
            str: parseable entity name
        """
        name = self.remove_disambiguation()
        name = re.sub(r" ", "_", name)
        name = re.sub(r"\W", "", name)
        return name

    def parseable_original(self):
        """Returns the parseable original word of the entity, e.g. the original
         word in such a way that it will not be separated by the parser but
         treated as single word.

        Returns:
            str: parseable entity original
        """
        original = re.sub(r" ", "_", self.original)
        original = re.sub(r"\W", "", original)
        return original

    def to_entity_format(self, include_orig=True, nospace_category=False):
        """Returns the entity in the format [<name>|<category|<original>].

        Or if include_orig is false in the format [<name>|<category>].

        Args:
            include_orig (bool): whether to include the original word
            nospace_category (bool) whether to replace spaces in the category

        Returns:
            str: entity string
        """
        category = self.category
        if nospace_category:
            category = self.category.replace(" ", "_")

        name = self.name
        if self.id:
            name = self.id + ":" + self.name

        if include_orig:
            return "[" + name + "|" + category + "|" + \
                    self.original + "]"
        return "[" + name + "|" + category + "]"

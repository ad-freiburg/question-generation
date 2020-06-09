# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prangen@informatik.uni-freiburg.de>

import unittest
import os
import sys
import inspect
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from entity import Entity


class EntityTest(unittest.TestCase):

    def test_clean_name(self):
        e = Entity("The_Lord_of_the_Rings__The_Two_Towers", "Film", "film")
        clean_name = e.clean_name()
        self.assertEqual(clean_name, 'The Lord of the Rings: The Two Towers')

    def test_remove_disambiguation(self):
        e = Entity("Paris_(France)", "Location", "Paris")
        name = e.remove_disambiguation()
        self.assertEqual(name, 'Paris')
        e = Entity("Pat_Williams_(Author)_#6 ", "Person", "Pat")
        name = e.remove_disambiguation()
        self.assertEqual(name, 'Pat_Williams')
        e = Entity("Pat Williams (Author) #6 ", "Person", "Pat")
        name = e.remove_disambiguation()
        self.assertEqual(name, 'Pat Williams')

    def test_parseable_name(self):
        e = Entity("Children's_literature", "Field of Study", "book")
        name = e.parseable_name()
        self.assertEqual(name, 'Childrens_literature')
        e = Entity("Paris_(France)", "Location", "Paris")
        name = e.parseable_name()
        self.assertEqual(name, 'Paris')

    def test_to_entity_format(self):
        e = Entity("Children's_literature", "Field of Study", "book")
        mention = e.to_entity_format()
        self.assertEqual(mention, "[Children's_literature|Field of Study|book]")
        mention = e.to_entity_format(include_orig=False)
        self.assertEqual(mention, "[Children's_literature|Field of Study]")
        mention = e.to_entity_format(nospace_category=True)
        self.assertEqual(mention, "[Children's_literature|Field_of_Study|book]")


if __name__ == '__main__':
    unittest.main()

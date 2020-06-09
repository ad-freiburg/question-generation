# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prangen@informatik.uni-freiburg.de>

import unittest
import os
import sys
import inspect
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from utils import clean_sentence


class UtilsTest(unittest.TestCase):

    def test_clean_sentence(self):
        s = "[Actrius|Film|It] was shown at the 1997 [Film_Festival|Recurring event|Film Festival] ."
        sent, ents = clean_sentence(s)
        self.assertEqual(sent, "Actrius was shown at the 1997 Film_Festival .")
        self.assertEqual(str(ents[0]), '("Actrius", "Film", "It", 1)')
        self.assertEqual(str(ents[1]), '("Film_Festival", "Recurring event", "Film Festival", 7)')

        s = "[Paris_(France)|Location|Paris] is in France ( test ) , not in Germany ."
        sent, ents = clean_sentence(s)
        self.assertEqual(sent, "Paris is in France , not in Germany .")

        s = "The [Actrius|Film|film] first aired in the [Paris_(France)|Location|city] ."
        sent, ents = clean_sentence(s, remove_article=True)
        self.assertEqual(sent, "Actrius first aired in Paris .")
        self.assertEqual(str(ents[0]), '("Actrius", "Film", "film", 1)')
        self.assertEqual(str(ents[1]), '("Paris_(France)", "Location", "city", 5)')

        sent, ents = clean_sentence(s, use_singleword_originals=True, remove_article=False)
        self.assertEqual(sent, "The film first aired in the city .")
        self.assertEqual(str(ents[0]), '("Actrius", "Film", "film", 2)')
        self.assertEqual(str(ents[1]), '("Paris_(France)", "Location", "city", 7)')

        s = "More than 9 100 102 people lived there in 1992 ."
        sent, ents = clean_sentence(s)
        self.assertEqual(sent, "More than 9,100,102 people lived there in 1992 .")


if __name__ == '__main__':
    unittest.main()

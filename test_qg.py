# Copyright 2020, University of Freiburg
# Author: Natalie Prange <prangen@informatik.uni-freiburg.de>

import unittest

import warnings
from utils import clean_sentence
from entity import Entity
from collections import defaultdict
from qg import QuestionGenerator, det_aux_word, get_plural, get_dependency_graph, recover_pronouns, rm_subclauses

QG = QuestionGenerator(parse_input=False, regard_entity_name=False)

PARSE = []
QG_RESULTS = defaultdict(list)
with open("test_parse.txt", "r", encoding="utf8") as file:
    parse_string = ""
    for line in file:
        if line == "\n":
            if parse_string:
                PARSE.append(parse_string)
                parse_string = ""
        else:
            parse_string += line
with open("test_qg_results.txt", "r", encoding="utf8") as file:
    for line in file:
        line = line.strip()
        num, question, answer = line.split("\t")
        num = int(num)
        QG_RESULTS[num].append((question, answer))


class QGTest(unittest.TestCase):

    def setUp(self):
        warnings.simplefilter("ignore", ResourceWarning)

    def test_get_plural(self):
        word = get_plural("fish")
        self.assertEqual("fishes", word)

        word = get_plural("quiz")
        self.assertEqual("quizzes", word)

        word = get_plural("tree")
        self.assertEqual("trees", word)

        word = get_plural("bus")
        self.assertEqual("buses", word)

        word = get_plural("baby")
        self.assertEqual("babies", word)

        word = get_plural("tray")
        self.assertEqual("trays", word)

    # Test dep_parse_sentence
    def test_dep_parse_sentence(self):
        qg_parse = QuestionGenerator(parse_input=True, regard_entity_name=False)
        sent = "Mary has a dog ."
        dep_graph = get_dependency_graph(qg_parse.spacy_parser.parse_line(sent))
        n = dep_graph.nodes[2]
        self.assertEqual('root', n['rel'])
        self.assertEqual('has', n['word'])
        self.assertEqual('VBZ', n['tag'])
        self.assertEqual(0, n['head'])
        self.assertEqual(2, n['address'])
        self.assertEqual(None, n['entity'])

        sent, ents = clean_sentence("[Mary_X|Person|Mary] has a dog .")
        n = get_dependency_graph(qg_parse.spacy_parser.parse_line(sent)).nodes[1]
        self.assertEqual(None, n['entity'])

    # Test det_wh_word
    def test_det_wh_word(self):
        # Alibi dep graph.
        dep_graph = get_dependency_graph(PARSE[0])
        dep_graph_city = get_dependency_graph(PARSE[21])
        dep_graph_pl = get_dependency_graph(PARSE[22])

        e1 = Entity("Angela Merkel", "Person", "Angela")
        q_list = []
        q_list_city = ["city"]
        res = QG.det_wh_word(e1, q_list, dep_graph.get_root(), False)
        self.assertEqual(['Who'], res)

        e2 = Entity("Test Entity", "Event", "X")
        res = QG.det_wh_word(e2, q_list, dep_graph.get_root(), False)
        self.assertEqual(['What'], res)

        e3 = Entity("Potsdam", "Location", "Potsdam")
        res = QG.det_wh_word(e3, q_list, dep_graph.get_root(), True)
        self.assertEqual(['Which german city', 'Which city', 'Which town', 'What'], res)

        res = QG.det_wh_word(e3, q_list_city, dep_graph_city.get_root(), True)
        self.assertEqual(['Which german city', 'What'], res)

        e4 = Entity("Indian philosophy", "Field of Study", "Indian philosophies")
        res = QG.det_wh_word(e4, q_list, dep_graph_pl.get_root(), True)
        self.assertEqual(['Which fields of study', 'What'], res)

    # Test det_aux_word
    def test_det_aux_word(self):
        aux_list = [["does"], ["do"], ["did"], [], ["was"]]
        aux_pass_list = [[], [], [], ["was"], []]
        for i in range(5):
            dep_graph = get_dependency_graph(PARSE[i])
            root = dep_graph.get_root()
            infinitive = QG.lemmatizer.lemmatize(root['word'], 'v')
            aux = det_aux_word(root, infinitive, dep_graph)
            self.assertEqual(aux_list[i], aux[0])
            self.assertEqual(aux_pass_list[i], aux[1])

    def test_rm_subclauses(self):
        sents = ["[Rain_Man|Film|Rain Man] depicts a character with "
                 "[Autism_Society_of_America|Organisation|autism] who has "
                 "incredible talents and abilities ."]
        sents.append("Most children with [Autism|Disease or medical condition"
                     "|autism] acquire [Language_acquisition|Field Of Study|"
                     "language] by age five or younger")
        sents.append("the medical student [Jean_Marc_Gaspard_Itard|Person|Jean"
                     " Itard] treated [Jean_Marc_Gaspard_Itard|Person|him] "
                     "with a behavioral program designed to help "
                     "[Jean_Marc_Gaspard_Itard|Person|him] form social "
                     "attachments and to induce speech via imitation .")
        sents.append("The [New_Latin|Language Dialect|New Latin] word autismus"
                     " was coined by the [Switzerland|Location|Swiss] "
                     "psychiatrist [Eugen_Bleuler|Person|Eugen Bleuler] in "
                     "1910 as [Eugen_Bleuler|Person|he] was defining symptoms "
                     "of [Schizophrenia|Disease or medical condition|"
                     "schizophrenia] .")
        sents.append("[Hans_Asperger|Person|Asperger] was investigating an ASD"
                     " now known as [Asperger_syndrome|Disease or medical "
                     "condition|Asperger syndrome]")
        for i in range(5):
            dep_graph = get_dependency_graph(PARSE[i])
            rm_subclauses(dep_graph)
            self.assertEqual(sents[i], dep_graph.to_sentence())

    def test_correct_entity_recognition(self):
        sents = []
        sents.append(["[Albert_Einstein|Person|Albert]", "[Albert_Einstein|Person|Einstein]"])
        sents.append(["[University_of_Calgary|University|University]", "of",
                      "[University_of_Calgary|Location|Calgary]"])
        sents.append(["[University_of_Calgary|University|University]", "of", "[Alabama|Location|Alabama]"])
        sents.append(["The", "[The_Hobbit|Written_Work|Hobbit]"])
        sents.append(["[American_History_X|Film|American History]", "X"])
        results = []
        results.append(["[Albert_Einstein|Person|Albert Einstein]"])
        results.append(["[University_of_Calgary|University|University of Calgary]"])
        results.append(["[University_of_Calgary|University|University]", "of", "[Alabama|Location|Alabama]"])
        results.append(["[The_Hobbit|Written_Work|The Hobbit]"])
        results.append(["[American_History_X|Film|American History X]"])

        for i in range(len(sents)):
            new_sent = QG.correct_entity_recognition(sents[i])
            self.assertEqual(results[i], new_sent)

    def test_recover_pronouns(self):
        results = []
        results.append("It is [Alice|Person|her] book .")
        results.append("[Bob|Person|He] gave it to [Alice|Person|her] .")
        results.append("[Alice|Person|Alice] wrote her first book in 1992 .")
        results.append("[Charly|Person|He] was [Bob|Person|his] friend .")
        results.append("[Charly|Person|He] wrote his first book in 1992 .")
        for i in range(15, 20):
            dep_graph = get_dependency_graph(PARSE[i])
            recover_pronouns(dep_graph)
            sent = dep_graph.to_sentence()
            self.assertEqual(results[i-15], sent)

    # Test question generation
    def test_generate_question(self):
        for i, parse_str in enumerate(PARSE):
            questions, original = QG.generate_question(parse_str, False)
            if i+1 in QG_RESULTS:
                if len(questions) > 0:
                    self.assertEqual(QG_RESULTS[i+1], questions)
                else:
                    self.assertEqual(QG_RESULTS[i+1], [])
            else:
                self.assertEqual([], questions)


if __name__ == '__main__':
    unittest.main()

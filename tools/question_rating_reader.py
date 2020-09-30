from typing import Tuple, Any

import json

from tools.generated_question import GeneratedQuestion
from tools.question_rating import QuestionRatingValue


class QuestionRatingReader:
    @staticmethod
    def get_rated_question(dump) -> Tuple[GeneratedQuestion, Any]:
        question = GeneratedQuestion.from_json(dump)
        results = json.loads(dump)["results"]
        for criteria, val in results.items():
            results[criteria] = QuestionRatingValue.get_value_from_string(val.lower())
        return question, results

    @staticmethod
    def read_from_file(json_file):
        with open(json_file, 'r', encoding='utf8') as file:
            for line in file:
                yield QuestionRatingReader.get_rated_question(line)

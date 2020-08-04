from typing import Iterator, Dict

import csv

from tools.generated_question import GeneratedQuestion
from tools.question_rating import QuestionRatingValue, QuestionRatingCriteria


class CrowdSourcingAssignment:
    def __init__(self,
                 question: GeneratedQuestion,
                 rating: Dict[QuestionRatingCriteria, QuestionRatingValue],
                 worker_id: str,
                 work_time: int):
        self.question = question
        self.rating = rating
        self.worker_id = worker_id
        self.work_time = work_time

    @staticmethod
    def assignment_reader(assignment_file: str) -> Iterator["CrowdSourcingAssignment"]:
        with open(assignment_file) as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for i, row in enumerate(csv_reader):
                # Skip column title row
                if i == 0:
                    continue

                generated_question = GeneratedQuestion(row["Input.question"],
                                                       row["Input.answer"],
                                                       row["Input.paragraph"],
                                                       row["Input.question_id"],
                                                       row["Input.method"])

                rating = dict()
                answer_cols = [(col_name, col_value) for col_name, col_value in sorted(row.items())
                               if col_name.startswith("Answer.")]
                for answer_col_name, answer_col_value in answer_cols:
                    criteria, criteria_val = answer_col_name[len("Answer."):-len(".on")].split("-")
                    if answer_col_value == "true":
                        rating_criteria = QuestionRatingCriteria.get_criteria_from_string(criteria)
                        rating_value = QuestionRatingValue.get_value_from_string(criteria_val)
                        rating[rating_criteria] = rating_value

                if len(rating) < 5:
                    for c in [QuestionRatingCriteria.GRAMMAR, QuestionRatingCriteria.MEANINGFULNESS,
                              QuestionRatingCriteria.NATURALNESS, QuestionRatingCriteria.SPECIFICITY,
                              QuestionRatingCriteria.VALIDITY]:
                        if c not in rating:
                            rating[c] = QuestionRatingValue.NONE_SELECTED

                # If question was rated as not grammatical or not meaningful, set all other criteria to N/A
                ignore_next = {QuestionRatingValue.NO, QuestionRatingValue.NA, QuestionRatingValue.NONE_SELECTED}
                if rating[QuestionRatingCriteria.GRAMMAR] in ignore_next:
                    rating[QuestionRatingCriteria.MEANINGFULNESS] = QuestionRatingValue.NA
                if rating[QuestionRatingCriteria.MEANINGFULNESS] in ignore_next:
                    rating[QuestionRatingCriteria.NATURALNESS] = QuestionRatingValue.NA
                    rating[QuestionRatingCriteria.VALIDITY] = QuestionRatingValue.NA
                    rating[QuestionRatingCriteria.SPECIFICITY] = QuestionRatingValue.NA

                assignment = CrowdSourcingAssignment(generated_question,
                                                     rating,
                                                     row["WorkerId"],
                                                     row["WorkTimeInSeconds"])
                yield assignment

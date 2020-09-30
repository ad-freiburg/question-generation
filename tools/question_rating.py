from enum import Enum


class QuestionRatingValue(Enum):
    NO = 0
    BORDERLINE = 1
    YES = 2
    NA = -1
    NONE_SELECTED = -2

    @staticmethod
    def get_value_from_string(string: str):
        if string == "no":
            return QuestionRatingValue.NO
        elif string == "borderline":
            return QuestionRatingValue.BORDERLINE
        elif string == "yes":
            return QuestionRatingValue.YES
        elif string == "na":
            return QuestionRatingValue.NA
        else:
            raise ValueError("Question Rating Value %s not known" % string)

    def __lt__(self, other):
        return self.value < other.value


class QuestionRatingCriteria(Enum):
    GRAMMAR = 0
    MEANINGFULNESS = 1
    NATURALNESS = 2
    VALIDITY = 3
    SPECIFICITY = 4

    @staticmethod
    def get_criteria_from_string(string: str):
        if string == "grammar":
            return QuestionRatingCriteria.GRAMMAR
        elif string == "meaning":
            return QuestionRatingCriteria.MEANINGFULNESS
        elif string == "naturalness":
            return QuestionRatingCriteria.NATURALNESS
        elif string == "validity":
            return QuestionRatingCriteria.VALIDITY
        elif string == "specificity":
            return QuestionRatingCriteria.SPECIFICITY
        else:
            raise ValueError("Question Rating Criteria %s not known" % string)

    def __lt__(self, other):
        return self.value < other.value

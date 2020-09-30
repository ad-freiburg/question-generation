from typing import Optional, Iterator

from enum import Enum

from tools.generated_question import GeneratedQuestion


class QuestionFormat(Enum):
    TSV = 0
    JSON = 1


class QuestionReader:
    @staticmethod
    def get_question(line: str, question_format: QuestionFormat, method: str) -> GeneratedQuestion:
        if question_format == QuestionFormat.TSV:
            delimiter = "\t"
            line = line.strip("\n")
            sentence_id, question, answer, paragraph = line.split(delimiter)
            return GeneratedQuestion(question, answer, paragraph, sentence_id, method, sentence_id)
        elif question_format == QuestionFormat.JSON:
            return GeneratedQuestion.from_json(line)

    @staticmethod
    def question_iterator(file_path: str,
                          n: int,
                          question_format: Optional[QuestionFormat] = QuestionFormat.TSV,
                          method: Optional[str] = "Unknown") -> Iterator[GeneratedQuestion]:
        with open(file_path, "r", encoding='utf8') as file:
            for i, line in enumerate(file):
                if i == n:
                    break
                yield QuestionReader.get_question(line, question_format, method)

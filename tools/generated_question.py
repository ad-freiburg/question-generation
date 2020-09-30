from typing import Optional, Dict

import json


class GeneratedQuestion:
    def __init__(self,
                 question: str,
                 answer: str,
                 paragraph: str,
                 id: Optional[str] = None,
                 method: Optional[str] = None,
                 sentence_id: Optional[int] = None):
        self.question = question
        self.answer = answer
        self.paragraph = paragraph
        self.id = id
        self.method = method
        self.sentence_id = sentence_id

    def to_dict(self) -> Dict:
        data = {"question": self.question,
                "answer": self.answer,
                "paragraph": self.paragraph}
        if self.id is not None:
            data["id"] = self.id
        if self.method is not None:
            data["method"] = self.method
        if self.sentence_id is not None:
            data["sentence_id"] = self.sentence_id
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @staticmethod
    def from_dict(data):
        return GeneratedQuestion(data["question"],
                                 data["answer"],
                                 data["paragraph"],
                                 id=data["id"] if "id" in data else None,
                                 method=data["method"] if "method" in data else None,
                                 sentence_id=data["sentence_id"] if "sentence_id" in data else None)

    @staticmethod
    def from_json(dump):
        return GeneratedQuestion.from_dict(json.loads(dump))

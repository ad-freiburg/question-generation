from typing import List, Tuple, Dict, Iterator

import argparse
import json
import random
from termcolor import colored

from tools.generated_question import GeneratedQuestion
from tools.own_evaluation_summarizer import OwnEvaluationSummarizer
from tools.question_rating import QuestionRatingValue
from tools.question_rating_reader import QuestionRatingReader
from tools.question_reader import QuestionReader, QuestionFormat


class EvaluationCriteria:
    def __init__(self, name, text):
        self.name = name
        self.text = text


evaluation_criteria = (EvaluationCriteria("grammar", "Grammatically correct?"),
                       EvaluationCriteria("naturalness", "Does the question sound natural?"),
                       EvaluationCriteria("context", "Is it clear what the question refers to - is necessary context given?"),
                       EvaluationCriteria("answerability", "Is the question specific enough to be theoretically answerable?"),
                       EvaluationCriteria("question_word", "Is the question word correct?"),
                       EvaluationCriteria("nerd_question", "If entities in the question are replaced by their text & meaning, is the meaning preserved (or clarified)?"),
                       EvaluationCriteria("nerd_answer", "If entities in the answer are replaced by their text & meaning, is the meaning preserved (or clarified)?"))


def to_dict(question: GeneratedQuestion, results: List[Tuple[str, QuestionRatingValue]]) -> Dict:
    data = question.to_dict()
    results_dict = dict()
    for criteria, val in results:
        results_dict[criteria] = val.name
    data["results"] = results_dict
    return data


def get_user_rating() -> List[Tuple[str, QuestionRatingValue]]:
    results = []
    for criteria in evaluation_criteria:
        while True:
            response = input(colored(criteria.name + ": ", attrs=['bold']) + criteria.text + " ")
            result = None
            if response.lower() == "y":
                result = QuestionRatingValue.YES
            elif response.lower() == "b":
                result = QuestionRatingValue.BORDERLINE
            elif response.lower() == "n":
                result = QuestionRatingValue.NO
            elif response == "Q":
                return
            else:
                print(colored("Please type one of the following values: {y, b, n}."
                              "If you want to stop the evaluation instead type \"Q\"", color='red'))

            if result:
                results.append((criteria.name, result))
                break
    return results


def get_question_from_random_iterator(question_iterators: List[Iterator[GeneratedQuestion]]) -> GeneratedQuestion:
    """Get the next question from a random question iterator.
    """
    exclude = set()
    question = None
    while len(exclude) != len(question_iterators):
        num_iterator = random.choice([i for i in range(len(question_iterators)) if i not in exclude])
        exclude.add(num_iterator)
        question = next(question_iterators[num_iterator], None)
        if question:
            break
    return question


def main(args):
    # Get a question iterator for each input file
    question_iterators = []
    for input_file in args.input_files:
        file_name = input_file[input_file.rfind("/") + 1:]
        question_iterator = QuestionReader.question_iterator(input_file,
                                                             args.num_questions,
                                                             question_format=QuestionFormat.TSV,
                                                             method=file_name)
        question_iterators.append(question_iterator)

    outfile = open(args.output_file, 'w', encoding='utf8')
    print(colored("Type \"Q\" if you want to stop the evaluation in between.", attrs=['bold']))
    print(colored("Answer the evaluation questions using [Y]es/[B]orderline/[N]o", attrs=['bold']))

    count = 0
    while True:
        count += 1
        question = get_question_from_random_iterator(question_iterators)
        if question is None:
            break
        print("*" * 120)
        print((str(count) + " ").ljust(120, "*"))
        print("*" * 120)
        print("%s %s" % (colored("Question:", attrs=['bold']), colored(question.question, color="green")))
        print("%s %s" % (colored("Answer:", attrs=['bold']), colored(question.answer, color="yellow")))
        print("%s %s" % (colored("Paragraph:", attrs=['bold']), colored(question.paragraph, color="blue")))
        print()
        results = get_user_rating()
        if results is None:
            print(colored("Stop evaluation.", color="red"))
            print()
            break
        print()
        json_results = json.dumps(to_dict(question, results))
        outfile.write(json_results + "\n")
    outfile.close()

    # Print evaluation summary
    method2results = OwnEvaluationSummarizer.get_method2results(QuestionRatingReader.read_from_file(args.output_file))
    OwnEvaluationSummarizer.print_evaluation_summary(method2results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input_files", type=str, required=True, nargs='+',
                        help="File containing filtered questions")

    parser.add_argument("-o", "--output_file", type=str, required=True,
                        help="Output file")

    parser.add_argument("-n", "--num_questions", type=int,
                        help="Number of questions to be evaluated from each file.")

    main(parser.parse_args())

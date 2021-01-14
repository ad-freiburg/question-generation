import argparse

from tools.own_evaluation_summarizer import OwnEvaluationSummarizer
from tools.question_rating_reader import QuestionRatingReader


def main(args):
    method2results = OwnEvaluationSummarizer.get_method2results(QuestionRatingReader.read_from_file(args.input_file))
    perfect_questions = OwnEvaluationSummarizer.get_perfect_questions(
        QuestionRatingReader.read_from_file(args.input_file))
    OwnEvaluationSummarizer.print_evaluation_summary(method2results, perfect_questions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input_file", type=str, required=True,
                        help="Input file containing one json object per line.")

    main(parser.parse_args())

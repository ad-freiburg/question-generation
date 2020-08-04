import argparse
from tools.crowd_sourcing_assignment import CrowdSourcingAssignment
from tools.question_rating import QuestionRatingValue


def get_results(input_file):
    results = dict()
    for assignment in CrowdSourcingAssignment.assignment_reader(input_file):
        if assignment.question.method not in results:
            results[assignment.question.method] = dict()
        for criteria, value in sorted(assignment.rating.items()):
            if criteria not in results[assignment.question.method]:
                results[assignment.question.method][criteria] = []
            results[assignment.question.method][criteria].append(value)

    return results


def print_results(results):
    for method, result in sorted(results.items()):
        print("%s:" % method)
        for criteria, ratings in sorted(result.items()):
            scores = [max(r.value, 0) for r in ratings]
            num_yes = len([r.value for r in ratings if r == QuestionRatingValue.YES])
            num_borderline = len([r.value for r in ratings if r == QuestionRatingValue.BORDERLINE])
            num_no = len([r.value for r in ratings if r == QuestionRatingValue.NO])
            num_na = len([r.value for r in ratings if r == QuestionRatingValue.NA])
            num_none = len([r.value for r in ratings if r == QuestionRatingValue.NONE_SELECTED])
            print("\t%s:\t%f\t%d x %s\t%d x %s\t%d x %s\t%d x %s\t%d x %s"
                  % (criteria.name, sum(scores) / len(scores), num_yes, QuestionRatingValue.YES.name,
                     num_borderline, QuestionRatingValue.BORDERLINE.name, num_no, QuestionRatingValue.NO.name,
                     num_na, QuestionRatingValue.NA.name, num_none, QuestionRatingValue.NONE_SELECTED.name))
        print()


def main(args):
    results = get_results(args.input_file)
    print_results(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input_file", type=str, default=None,
                        help="Input csv file as provided by Amazon MTurk.")

    main(parser.parse_args())

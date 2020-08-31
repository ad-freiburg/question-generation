import argparse
from tools.crowd_sourcing_assignment import CrowdSourcingAssignment
from tools.question_rating import QuestionRatingValue


def get_results_by_method(input_file):
    results = dict()
    for assignment in CrowdSourcingAssignment.assignment_reader(input_file, False):
        if assignment.question.method not in results:
            results[assignment.question.method] = dict()
        for criteria, value in sorted(assignment.rating.items()):
            if criteria not in results[assignment.question.method]:
                results[assignment.question.method][criteria] = []
            results[assignment.question.method][criteria].append(value)

    return results


def get_results_by_question(input_file):
    results = dict()
    for assignment in CrowdSourcingAssignment.assignment_reader(input_file, False):
        if assignment.question.question_id not in results:
            results[assignment.question.question_id] = dict()
        for criteria, value in sorted(assignment.rating.items()):
            if criteria not in results[assignment.question.question_id]:
                results[assignment.question.question_id][criteria] = []
            results[assignment.question.question_id][criteria].append(value)

    return results


def print_results(results):
    print("*"*100)
    print("Crowd sourcing evaluation results")
    print("Scores are computed as average scores where YES=2, BORDERLINE=1, NO/NA/NONE_SELECTED=0")
    # print("If a question was rated as not grammatical or not meaningful, all other criteria were set to N/A")
    print("*"*100)
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


def print_inter_rater_agreement(results):
    print("*" * 100)
    print("Inter-rater agreement")
    print("Percentage of questions that received both \"yes\" and \"no\" answers")
    print("*" * 100)
    rater_disagreements = dict()
    for question_id, result in sorted(results.items()):
        for criteria, ratings in sorted(result.items()):
            if QuestionRatingValue.NO in ratings and QuestionRatingValue.YES in ratings:
                if criteria not in rater_disagreements:
                    rater_disagreements[criteria] = 0
                rater_disagreements[criteria] += 1

    for criteria, num_disagreements in sorted(rater_disagreements.items()):
        percentage = num_disagreements / len(results) * 100
        print("%s: %.2f%% (%d/%d)"
              % (criteria.name, percentage, num_disagreements, len(results)))


def main(args):
    results_by_method = get_results_by_method(args.input_file)
    print_results(results_by_method)
    results_by_question = get_results_by_question(args.input_file)
    print_inter_rater_agreement(results_by_question)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input_file", type=str, default=None,
                        help="Input csv file as provided by Amazon MTurk.")

    main(parser.parse_args())

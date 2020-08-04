import argparse
from tools.crowd_sourcing_assignment import CrowdSourcingAssignment


def main(args):
    for assignment in CrowdSourcingAssignment.assignment_reader(args.input_file):
        if args.worker_id and assignment.worker_id != args.worker_id:
            continue
        if args.question_id and assignment.question.question_id != args.question_id:
            continue
        print("*" * 80)
        print(assignment.question.question)
        print(assignment.question.answer)
        print("---")
        for criteria, value in assignment.rating.items():
            print("%s:\t%s" % (criteria.name, value.name))
        print("---")
        print("method: %s\tquestion id: %s\tworker id: %s\twork time: %ds" %
              (assignment.question.method, assignment.question.question_id, assignment.worker_id, assignment.work_time))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-i", "--input_file", type=str, default=None,
                        help="Input csv file as provided by Amazon MTurk.")

    parser.add_argument("--worker_id", type=str, default=None,
                        help="If provided, only assignments processed by the worker with the given id are displayed")

    parser.add_argument("--question_id", type=str, default=None,
                        help="If provided, only assignments for the given question are displayed")

    main(parser.parse_args())

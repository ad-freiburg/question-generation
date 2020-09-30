from termcolor import colored


class OwnEvaluationSummarizer:
    @staticmethod
    def get_method2results(iterable_results):
        all_results = dict()
        for question, results in iterable_results:
            for criteria, val in results.items():
                if question.method not in all_results:
                    all_results[question.method] = dict()
                if criteria not in all_results[question.method]:
                    all_results[question.method][criteria] = dict()
                if val not in all_results[question.method][criteria]:
                    all_results[question.method][criteria][val] = 0
                all_results[question.method][criteria][val] += 1
        return all_results

    @staticmethod
    def print_evaluation_summary(method2results):
        print("*" * 120)
        print(colored("Evaluation summary:", attrs=['bold']))
        for method, results in method2results.items():
            print("%s:" % colored(method, attrs=['underline']))
            for criteria in sorted(results):
                print("%s:\t" % colored(criteria), end="")
                num_total = 0
                scores = []
                for rating_value in sorted(results[criteria], reverse=True):
                    num_occurrences = results[criteria][rating_value]
                    scores.append(max(rating_value.value, 0) * num_occurrences * 0.5)
                    num_total += num_occurrences
                    print("%s x %s\t" % (str(num_occurrences).rjust(3, " "), rating_value.name.lower()), end="")
                print("%.2f" % (sum(scores) / num_total))
            print()

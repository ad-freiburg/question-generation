"""
Tokenization Repair Paper, Submission to EMNLP 2020 

Script for testing the statistical significance of our results.

Modified by Natalie Prange <prange@cs.uni-freiburg.de>
"""

import sys
import math
import random
import os
import argparse


def accuracy_r_test_sampling(acc1, acc2, num_samples=1024):
    """
    Like above, but explicitly iterating over all assignments or using random
    sampling if there are too many.

    >>> accuracy_r_test_sampling([0], [1])
    1.0
    >>> accuracy_r_test_sampling([0, 0, 0], [1, 0, 0])
    1.0
    >>> accuracy_r_test_sampling([0, 0], [1, 1])
    0.5
    >>> accuracy_r_test_sampling([0.5, 0.7], [0.2, 0.4])
    0.5
    >>> accuracy_r_test_sampling([0.5, 0.6, 0.4], [0.4, 0.2, 0.5])
    0.75
    """

    assert len(acc1) == len(acc2)
    n = len(acc1)
    use_random_sampling = (math.log2(num_samples) < n)
    if math.log2(num_samples) > n:
        num_samples = 2**n
    diff_observed = sum([acc1[i] - acc2[i] for i in range(n)]) / n
    # print("%40s: %5.2f%%" % ("difference", abs(100 * diff_observed)))

    # Now count the number of assignments for which the diff is >= the observed
    # diff.
    # 
    # NOTE: We consider absolute values, that is, a diff of -5.3 is considered
    # >= a diff of 4.2 although the diff is in the opposite direction. This
    # makes sense under the null hypothesis that the two sequences come from the
    # same random process.
    count = 0
    for i in range(num_samples):
        # Compute the next assignment as a 0-1 sequence of length n (where 1
        # means swapping the two respective elements from acc1 and acc2).
        if use_random_sampling:
            assignment = "".join([str(random.randint(0, 1)) for _ in range(n)])
        else:
            assignment = format(i, "0" + str(n) + "b")
        # Compute the mean difference between A and B using this assignment. In
        # the swap array, simply map "0" -> +1 and "1" -> - 1.
        swap = [1 if x == "0" else -1 for x in assignment]
        diff = sum([(acc1[i] - acc2[i]) * swap[i] for i in range(n)]) / n
        # print(diff, diff_observed)
        # print(swap, diff, diff_observed)
        if abs(diff) >= abs(diff_observed):
            count += 1

    return count / num_samples


def main(args):
    print("Number of samples used for randomization test: %d" % args.num_samples)
    print("Method 1: %s" % args.method1)
    print("Method 2: %s" % args.method2)
    sys.setrecursionlimit(10**6)

    results = {}
    metrics = {"MRR-1": 1, "MRR-2": 2, "RUI": 3, "P@5": 4, "AP": 5, "nDCG": 6}
    methods = {'nqg-zhao_short-answer_entityparse_1m_paragraph-fixed_wd_shuf_15ep': 1,
               'aq_qg-heilman_wd_1m_shuf_15ep': 2,
               'aq_keep-comma_entityparse_ren_1m_wd_shuf_15ep': 3,
               'aq_keep-comma_entityparse_1m_wd_shuf_15ep': 4}
    method_names = ["nqg-zhao", "qg-heilman", "ours (ren)", "ours"]

    file_list = []
    if args.dir:
        file_list = [os.path.join(args.dir, f) for f in sorted(os.listdir(args.dir))]
    elif args.method1 and args.method2:
        file_list = [args.method1, args.method2]
    else:
        print("Specify either a directory containing all files with --dir or two files with --method1 and --method2.")
        exit(1)

    for file_name in file_list:
        with open(file_name) as f:
            method = ""
            for m in methods.keys():
                if m in file_name:
                    method = m
            if not method:
                continue
            if method not in results:
                results[method] = (dict([(metric, []) for metric in metrics]))
            for line in f:
                if line.startswith("MRR-1: "):
                    score = float(line.strip().replace("MRR-1: ", ""))
                    results[method]["MRR-1"].append(score)
                elif line.startswith("MRR-2: "):
                    score = float(line.strip().replace("MRR-2: ", ""))
                    results[method]["MRR-2"].append(score)
                elif line.startswith("\tRUI: "):
                    score = float(line.strip().replace("RUI: ", ""))
                    results[method]["RUI"].append(score)
                elif line.startswith("P@5: "):
                    lst = line.split(",")
                    results[method]["P@5"].append(float(lst[0].strip().replace("P@5: ", "")))
                    results[method]["AP"].append(float(lst[1].strip().replace("AP: ", "")))
                    results[method]["nDCG"].append(float(lst[2].strip().replace("nDCG@5: ", "")))

    print()
    print("All metrics: %s" % metrics)
    print("All methods: %s" % results.keys())
    print()

    # Iterate over all or some combinations and show the difference in the
    # accuracy and the p-value for some or a selection, depending on the input
    # arguments (see usage info above).
    for i, method1 in enumerate(sorted(results.keys(), key=lambda x: methods[x])):
        for j, method2 in enumerate(sorted(results.keys(), key=lambda x: methods[x])):
            if j <= i:
                continue

            print("*" * 80)
            print(method1)
            print(method2)
            print("*" * 80)
            for metric in sorted(metrics, key=lambda x: metrics[x]):
                if len(results[method1][metric]) == 0 or len(results[method2][metric]) == 0:
                    continue

                print("Results for metric %s" % metric)
                acc_1 = results[method1][metric]
                acc_2 = results[method2][metric]
                assert len(acc_1) == len(acc_2)
                mean_1 = sum(acc_1) / len(acc_1)
                mean_2 = sum(acc_2) / len(acc_2)
                print("%24s: %5.2f%%" % (method_names[methods[method1] - 1], 100 * mean_1))
                print("%24s: %5.2f%%" % (method_names[methods[method2] - 1], 100 * mean_2))
                print("%24s: %5.2f%%" % ("difference", 100 * abs(mean_1 - mean_2)))
                p_value_sampled = accuracy_r_test_sampling(acc_1, acc_2, args.num_samples)
                print("%24s:  %.3f" % ("p-value sampled", p_value_sampled))
                print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")

    parser.add_argument("-n", "--num_samples", type=int, default=2048,
                        help="Number of samples for random sampling")

    parser.add_argument("--dir", type=str, default=None,
                        help="Directory containing all results")

    parser.add_argument("--method1", type=str, default=None,
                        help="File containing results for method 1")

    parser.add_argument("--method2", type=str, default=None,
                        help="File containing results for method 2")

    main(parser.parse_args())

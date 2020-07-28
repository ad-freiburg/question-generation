import argparse
import re


def remove_entity_mentions(sentence):
    """Replace entity mentions by the original word.

    Entity mentions are of the form [<entity_name>|<original_word>]
    or [<entity_name>|<type>|<original_word>] by the original word.

    Args:
        sentence (str): the input sentence

    Returns:
        str: sentence without entity mentions
    """
    return re.sub(r"\[.*?\|([^\[\]]*?\|)?(.*?)\]", r"\2", sentence)


def main(args):
    outfile = None
    if args.output_file:
        outfile = open(args.output_file, "w", encoding="utf8")

    with open(args.input_file, "r", encoding="utf8") as file:
        for i, line in enumerate(file):
            sentence = remove_entity_mentions(line)
            if outfile:
                outfile.write(sentence)
            else:
                print(sentence.strip("\n"))

            if args.num_lines > 0 and i >= args.num_lines - 1:
                break

    if outfile:
        outfile.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--num_lines", default=0, type=int,
                        help="Maximum number of lines to process.")
    parser.add_argument("input_file", type=str,
                        help="Input file that contains sentences with entity mentions.")
    parser.add_argument("-o", "--output_file", default="", type=str,
                        help="Output file to which to write the processed sentences to.")
    main(parser.parse_args())

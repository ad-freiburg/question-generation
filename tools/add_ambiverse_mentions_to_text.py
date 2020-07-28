import argparse
import logging
import sys
import os
import inspect
import json


current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from entity import Entity
import config

logging.basicConfig(format='%(asctime)s: %(message)s', datefmt="%H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

QID_TO_LABEL_FILE = config.WIKIDATA_MAPPINGS + "qid_to_label_all.txt"
QID_TO_CATEGORIES_FILE = config.WIKIDATA_MAPPINGS + "qid_to_categories_v9.txt"


def read_qid_to_category(file):
    qid_to_category = dict()
    logger.info("Reading %s file..." % file)
    with open(file, "r", encoding="utf8") as file:
        for line in file:
            line = line.strip()
            qid, primary, secondary = line.split("\t")
            qid_to_category[qid] = (primary, secondary)
    return qid_to_category


def read_qid_to_label(file):
    qid_to_label = dict()
    logger.info("Reading %s file..." % file)
    with open(file, "r", encoding="utf8") as file:
        for line in file:
            line = line.strip()
            qid, label = line.split("\t")
            qid_to_label[qid] = label
    return qid_to_label


def get_qid_from_url(url):
    url = url.strip()
    url = url.strip("/")
    start_ind = url.rfind("/")
    return url[start_ind + 1:]


def main(args):
    if args.debug:
        logger.setLevel(logging.DEBUG)

    qid_to_label = read_qid_to_label(QID_TO_LABEL_FILE)
    qid_to_category = read_qid_to_category(QID_TO_CATEGORIES_FILE)
    with open(args.entity_file, "r", encoding="utf8") as f:
        json_obj = json.load(f)
        matches = json_obj["matches"]
        entities = json_obj["entities"]

        entity_is_concept = dict()
        for ent in entities:
            qid = get_qid_from_url(ent["id"])
            entity_is_concept[qid] = ent["type"] == "CONCEPT"
        for m in matches:
            url = m["entity"].get("id")
            qid = ""
            if url:
                qid = get_qid_from_url(url)
            m["is_concept"] = entity_is_concept.get(qid, False)

        matches.sort(key=lambda x: x["charOffset"])

    with open(args.text_file, "r", encoding="utf8") as text_file:
        line_offset = 0
        entity_index = 0
        new_text = ""
        for line in text_file:
            new_line = ""
            last_end_ind = 0
            if entity_index < len(matches):
                char_offset = matches[entity_index]["charOffset"]
                while line_offset <= char_offset < line_offset + len(line):
                    # Get entity span in text
                    start_ind = char_offset - line_offset
                    end_ind = start_ind + matches[entity_index]["charLength"]
                    entity_orig = line[start_ind:end_ind]
                    is_concept = matches[entity_index]["is_concept"]

                    if not is_concept or args.concept:
                        # Get entity information to form a proper mention
                        url = matches[entity_index]["entity"].get("id")
                        if url:
                            qid = get_qid_from_url(url)
                            entity_label = qid_to_label.get(qid, "")
                            entity_type = qid_to_category.get(qid, "")
                            if args.pretty_print and len(entity_type) > 0:
                                start_ind_primary = entity_type[0].find(":") + 1
                                entity_type = entity_type[0][start_ind_primary:]
                            else:
                                entity_type = "/".join(entity_type)
                            entity_name = qid + ":" + entity_label
                            entity = Entity(entity_name, entity_type, entity_orig)
                            # Add line between last entity mention and new mention to new line
                            new_line += line[last_end_ind:start_ind]
                            new_line += entity.to_entity_format(nospace_category=True)
                        else:
                            new_line += line[last_end_ind:start_ind]
                            new_line += "[||" + line[start_ind:end_ind] + "]"

                        # Increment entity index
                        last_end_ind = end_ind
                    entity_index += 1

                    if entity_index >= len(matches):
                        break

                    char_offset = matches[entity_index]["charOffset"]
                # Add remaining part of the line
                new_line += line[last_end_ind:]
                if args.output_file:
                    new_text += new_line
                else:
                    print(new_line, end="")
            else:
                if args.output_file:
                    new_text += line
                else:
                    print(line, end="")
            line_offset += len(line)
        if args.output_file:
            output_file = open(args.output_file, "w", encoding="utf8")
            output_file.write(new_text)
        else:
            print()


if __name__ == "__main__":
    # Handle command line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument("-d", "--debug", default=False, action="store_true",
                        help="Print additional information for debugging.")

    parser.add_argument("--text_file", type=str, required=True,
                        help="File containing the original text without entity mentions")

    parser.add_argument("--entity_file", type=str, required=True,
                        help="JSON file containing the entity mentions as provided by the ambiverse pipeline")

    parser.add_argument("-out", "--output_file", type=str, default=None,
                        help="Output file. If not provided, output will be written to stdout")

    parser.add_argument("--concept",  default=False, action="store_true",
                        help="Include concept entity mentions")

    parser.add_argument("--pretty_print",  default=False, action="store_true",
                        help="Only print primary type instaed of QID:<primary>/QID:<secondary>.")

    main(parser.parse_args())

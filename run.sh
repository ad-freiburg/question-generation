#!/bin/bash

bold=$(tput bold)
normal=$(tput sgr0)

# Get input file from cmd line argument
if [ -z "$1" ] || [ -z "$2" ]
then
      echo "${bold}Usage: $0 <input_sentence_file> <output_tag>${normal}"
      exit 1
fi

gq_path="data/gq/"
fq_path="data/fq/"
ex_path="data/fq/excluded/"

mkdir -p ${gq_path}
mkdir -p ${fq_path}
mkdir -p ${ex_path}

gq_file="${gq_path}gq_$2.txt"
fq_file="${fq_path}fq_$2.txt"
ex_file="${ex_path}ex_$2.txt"

python3 qg.py -p < "$1" > "${gq_file}"
echo "${bold}Wrote generated questions to ${gq_file}${normal}"
python3 filter_questions.py -f "${ex_file}" < "${gq_file}" > "${fq_file}"
echo "${bold}Wrote filtered questions to ${fq_file}${normal}"

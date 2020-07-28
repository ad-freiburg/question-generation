# Question Generation

*A rule-based system for factoid question generation from sentences with entity mentions.*

## Run

### Parse sentences

To parse your input sentences with one sentence per line and entities in the format `[<name>|<category>|<original>]` run

    python3 spacy_parser.py < <input_sentences_file> > <parsed_sentences_file>

To use the spacy sentence tokenizer instead of assuming one sentence per line use the option `--spacy_sent_tokenizer`.

To parse input sentences with Wikidata entities in the format `[<QID>:<label>|<category>|<original>]` use the option `-wd`.


### Generate questions

To generate questions from parsed sentences run

    python3 qg.py < <parsed_sentences_file> > <generated_questions_file>
    
Use the option `-wd` for Wikidata entities.

If you want to generate questions directly from input sentences use the option `-p`.
This will parse the input on-the-fly without creating an additional parse file.
Use the option `--spacy_sent_tokenizer` to use the spacy sentence tokenizer instead of assuming one sentence per line.

### Filter questions

To filter the generated questions run

    python3 filter_questions.py < <generated_questions_file> > <filtered_questions_file>


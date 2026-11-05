# RFQ parser: how to run
    pip install -r requirements.txt          # nothing to install (standard library only)
    python score.py my_tests.jsonl           # the company's scorer (not included with the brief; add it here, do not edit it)
    python score_local.py my_tests.jsonl     # our stand-in scorer (also: holdout.jsonl, redteam.jsonl)
    python -m unittest discover -s tests -v  # 25 unit tests
Files: parse.py (the function) | my_tests.jsonl (60) | holdout.jsonl (50) | redteam.jsonl (52) | tests/ | NOTE.md
make_tests.py / make_redteam.py regenerate the jsonl files.

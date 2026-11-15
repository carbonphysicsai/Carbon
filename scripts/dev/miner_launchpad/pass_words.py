"""The four public pass names a stopped grade can carry, each in one plain line.

``failure.pass`` of exam feedback v8 is one of these ids, else None (a stop in any other part of a grade, for example
the speed sample, is counted the same way and shows no pass). The Motor kit page
(`kits/motor/HOW_YOURE_TESTED.md`) carries the same lines word for word; a test holds them equal and holds the ids equal
to the door's closed set. No counts, no cases, no seconds: what the pass is, nothing measured.
"""

PASS_IDS = ("graded_pass", "inference_pair", "menu_rowcheck", "early_stop")

PASS_LINES = {
    "graded_pass": "Your built model answers the hidden exam designs once, and its answers are scored.",
    "inference_pair": "Carbon runs your built model again in a fresh process on a secret sample of the exam designs it already answered, and the answers must match.",
    "menu_rowcheck": "Carbon checks that each of your model's design answers does not depend on which other designs are in the batch.",
    "early_stop": "Before the graded pass, a model projected to run past the limit is stopped early when the early stop is on; it counts as a try, like a timeout.",
}

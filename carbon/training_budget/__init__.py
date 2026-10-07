"""The Challenge-neutral training budget study and compute budget (TRAINING-BUDGET-01).

Every Challenge runs the same study (Phases A-H, rules R1-R11) with the same
code. What differs lives only in the Challenge's sheet (`sheet`, values the
owner sets) and its adapter (`adapter`, what its existing records define).
The first Challenge to use it is an instance, never the design: shared modules
here hold no Challenge-specific literal.
"""

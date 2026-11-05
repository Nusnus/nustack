"""Which of mutmut's mutants a run tests again, from what changed since its full run.

It reads mutmut's `mutants/` folder and what Git says changed since that folder's full
run, then readies the folder for a run that tests only what those changes reach.
"""

"""The sync of a vendored copy, from upstream's clone to its pull request.

It reads the copy's record, upstream's history and both copies from Git, compares
each file, stages the copy with its new record, and opens, updates, keeps or closes
the pull request with its description, or withdraws its branch.
"""

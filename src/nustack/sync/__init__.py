"""The writing-for-agents sync, from upstream's clone to its pull request.

It reads upstream's history and both copies from Git, compares each file, stages the
copy, and opens, updates or closes the pull request with its description.
"""

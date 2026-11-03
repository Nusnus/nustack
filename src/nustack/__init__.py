"""The development harness around the nustack plugin.

It checks the repository against nustack's structural rules, bundles the plugin,
prints its release notes, holds a release tag to main and the plugin version and
publishes the release, and syncs the vendored writing-for-agents copy through a pull
request that carries its review evidence.
"""

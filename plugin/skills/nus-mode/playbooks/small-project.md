# Small project

Small project starts a project only the user uses, within the task, such as an experiment or a one-off tool. It holds the code to the full bar, as [long term](../../principle-long-term/SKILL.md) asks of temporary code, and skips what serves other readers and later work: agreed standards, commit hooks, CI, a remote repository and docs, beyond a file its tools create. Once the project outgrows that, [align](align.md) adds what [new project](new-project.md) builds.

1. **Learn what the project does** by new project's *Learn what the project does*, keeping the lines in the session. Done when its done condition holds.
2. **Choose the stack and its tools** by new project's *Choose the stack and its tools*, for every job but commit hooks and CI. Done when its done condition holds for every job but those.
3. **Lay out the project** by new project's *Lay out the project*, in a local repository. Done when its done condition holds.
4. **Make the tools enforce the code bar.** One command runs every check the principles and language skills call for, the tests included, each at the strictest setting the principles allow. Break, one at a time, each check, and see the command fail. Give a check that fails on a project with no code yet a placeholder, as new project's *Make the tools enforce the standards* says. Done when the command runs every check the principles and language skills call for, the tests included, each at the strictest setting the principles allow; and it passes on the new project and fails when each check alone is broken by hand.
5. **Build what the request asks** by new project's *Build what the request asks*, with step 4's command as the project's checks, run before each commit. Done when its done condition holds, with step 4 in place of new project's *Make the tools enforce the standards*.
6. **Review your work** by new project's *Review your work*. Done when its done condition holds.

**Reply:** the stack and each tool with a one-line reason, the layout with one line per module, and the command that runs the project.

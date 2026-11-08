---
name: principle-long-term
description: "Changes built to last, so they are done once."
disable-model-invocation: true
triggers: [user]
---

# Long term

Build every change to last, whatever the task's size or the state of the code around it: work built to last is done once.

- **Treat performance as a requirement** from the first version.
- **Keep the full bar on temporary code.** A prototype or experiment meets the bar of code that ships.
- **Remove each problem at its cause.** When a fix feels like a patch, fix the flaw behind it, higher in the design.
- **Fix the flaw everywhere it appears.** A fix's scope is the flaw, not the place it was found: fix every instance in the project, in any form, in the same change.
- **Finish what you touch.** Settle every nitpick and take every polish opportunity in each file the change touches, and name each flaw you spot elsewhere.
- **Keep each exemption narrow.** An exemption from a check covers as little as the tool allows, with its reason beside it; where a check cannot reach, say so beside the rule and follow the rule anyway.
- **Keep in the repository only what stays true.** Text there says only what holds until its subject's purpose changes; plans, specs and notes stay in the PR or the session.

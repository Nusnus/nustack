---
name: principle-long-term
description: "Changes built to last, so they are done once."
disable-model-invocation: true
triggers: [user]
---

# Long term

Build every change to last, whatever the task's size or the state of the code around it: work built to last is done once.

- **Treat performance as a requirement** from the first version.
- **Explain each benchmark or eval result before you act on it or report it.** Write the result that would change your decision before the runs. Rule out what else could explain the result, such as work that failed, was skipped or came from a cache, or either side of a comparison left untuned. Give the result with its run count and spread; give a performance result with what bounds it, from a profile or counters taken during a run, and an eval result with whether it holds for each model it claims to cover.
- **Keep the full bar on temporary code.** A prototype or experiment meets the bar of code that ships.
- **Fix the cause, not the symptom.** Before you fix a problem, trace it to the flaw that produces it and fix that, higher in the design where it lives; a change that only hides what the flaw produces is a patch.
- **Fix the flaw everywhere it appears.** A fix's scope is the flaw, not the place it was found: fix every instance in the project, in any form, in the same change.
- **Replace the old form outright.** When you change a form, such as a signature, a setting, a format or a name, delete the old one, leaving no alias, shim, deprecation or flag that keeps it. Keep the old form, deprecated, only for what the change cannot migrate: an outside consumer promised a stable interface, data an earlier version stored beyond the change's reach, or an older version running mid-deploy. Name each one, and when it can go, beside the code that keeps the old form.
- **Finish what you touch.** Settle every nitpick and take every polish opportunity in each file the change touches, and name each flaw you spot elsewhere.
- **Keep each exemption narrow.** An exemption from a check covers as little as the tool allows, with its reason beside it; where a check cannot reach, say so beside the rule and follow the rule anyway.
- **Keep in the repository only what stays true.** Text there says only what holds until its subject's purpose changes; plans, specs and notes stay in the PR or the session.

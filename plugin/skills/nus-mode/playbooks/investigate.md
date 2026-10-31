# Investigate

Investigate finds why a problem happens, and the fix that would remove its cause so the problem cannot come back. The project stays as you found it, and the fix goes in the reply.

1. **Pin the problem down.** Write down what happens, what should happen, and how to tell the two apart, then reproduce it. When it happens only in one environment or only sometimes, gather the record of each time it happened instead: logs, traces, metrics or reports. Done when a check shows the problem on demand, or the record shows it happening.
2. **Decompose it.** Split the problem into independent parts, each a question with its own evidence. Done when each part can be answered without the others.
3. **Validate each part** from evidence you observe: running the code, its runtime record, its source, or its documentation. Where a small throwaway experiment can confirm or refute an answer, run it outside the project: a scratch script, a minimal reproduction, or a copy of the code with one change. Record what each answer rests on. Done when every part has an answer backed by evidence.
4. **Find the cause.** Combine the answers into one account of why the problem happens, traced back to the earliest point where a change removes it. Done when the account explains every observation from steps 1 and 3.
5. **Find the fix that removes the cause.** Prefer a change that makes the problem impossible, such as a type, a structure, a removed path or a check a tool enforces. Weigh each candidate by the friction rate it would leave, as [nus-mode](../SKILL.md) defines it, and against [long term](../../principle-long-term/SKILL.md), and recommend one that leaves fewer friction points than the code has now. Done when the recommended fix names the cause it removes and the friction points it removes and adds, and each rejected candidate has the reason it lost.

**Reply:** the problem, each part with its evidence, the cause, and the recommended fix with the friction points it removes and adds, and every rejected candidate with its reason.

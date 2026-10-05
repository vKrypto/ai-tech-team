Break the request into at most {max_steps} sequential steps for the team. For each step pick who does it:
- "architect": analyse, design, decide, write plans or answers
- "senior_engineer": change code/files for a focused change, with unit tests
- "tester": exercise and verify existing behaviour (run the app, API calls, browser, test suites)
- "team_lead": review existing work or code and judge it
- "pr_reviewer": review a GitHub pull request
- "scrum_master": GitHub project upkeep (issues, labels, milestones, boards) and progress reports
- "researcher": investigate (web, docs, browser) and report with sources
- "coding": a full coding sub-workflow (inspect, plan, implement, test, review) for a substantial change
- "research": a full research sub-workflow (plan, search, analyze, synthesize)
- "validation": a full validation sub-workflow (tester runs checks, team lead judges)
Prefer few steps; a simple question is one step. End your answer with the plan as a fenced JSON block:
```json
[{{"agent": "researcher", "instruction": "..."}}]
```

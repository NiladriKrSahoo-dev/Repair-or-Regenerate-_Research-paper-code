# Repair vs Regenerate pipeline

1. `pip install -r requirements.txt`; `export GEMINI_API_KEY=...        # or ANTHROPIC_API_KEY for --provider anthropic`
2. Put your tasks in `tasks/tasks.jsonl`, one per line: `{"id","fn","source"}` (e.g. exported from ULT; pick functions by eligibility rules fixed BEFORE running).
3. Smoke test (no API): `python run_experiment.py --tasks tasks/smoke_tasks.jsonl --mock --out /tmp/s.jsonl`
4. Real run: `python run_experiment.py --tasks tasks/tasks.jsonl --provider gemini --model <pinned-model-id> --thinking-budget 0 --budget 8000 --reps 3`
5. `python analyze.py runs.jsonl`

Design decisions to confirm with your advisor BEFORE the real run:
- Repair/regeneration only triggers when the shared initial candidate fails validity; if it passes, both policies are identical (a tie). `analyze.py` therefore also reports the initial-failure subset.
- Budget rule: a call is made only if used + est_input(chars/3) + max_output <= budget. Same rule for both policies.
- Mutants: own AST operators, frozen per (task, condition). Consider Cosmic Ray for the final study.
- Run generated code only inside a container/VM. `execute.py` uses a subprocess and timeout, which is not a security sandbox.
- Renaming validity is checked only by compilation; add a differential-execution check before claiming behaviour preservation.
- `MockBackend` results are meaningless. Never report them.

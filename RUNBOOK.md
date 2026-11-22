# Runbook: from nothing to a finished paper

Everything is built except the experiment itself. Do these in order. Never edit a result by hand.

## 0. Before spending money
- [ ] Show the design to your advisor/professor. Agree on: model, token budget, N functions.
- [ ] Novelty check: search for papers comparing repair vs equal-budget regeneration for unit tests. If one exists, reframe.
- [ ] Verify EVERY citation in references.bib (title, authors, venue, year, that it exists). Several are 2025-2026 and I could not verify them.

## 1. Setup (use a container or VM; generated code is untrusted)
    cd rr_pipeline
    pip install -r requirements.txt
    export GEMINI_API_KEY=...        # or ANTHROPIC_API_KEY for --provider anthropic

## 2. Get a pool of functions, then select (outcome-blind, BEFORE any model call)
Mac note: use `python3` and `python3 -m pip install -r requirements.txt` if `pip`/`python` are not found.
Pool option A (matches the paper): export ULT to JSONL (fields: id, function name, source).
Pool option B (works today, any code): clone some small pure-Python repos and extract:
    python3 extract_functions.py --root /path/to/cloned/repos --out pool.jsonl
Then select (strict filter; expect most functions to be excluded, so use a large pool of thousands):
    python3 select_tasks.py --inp pool.jsonl --n 20 --seed 2026
If you use option B, change the paper's Tasks subsection (it currently says ULT) and say which repos. Do NOT use the Python standard library as the pool for real results: models have seen it, and selection gives trivial functions.
(If your pool JSONL uses other field names, pass --id-key/--fn-key/--src-key.)

Old instructions:
Export ULT to JSONL with fields for id, function name, source, then:
    python select_tasks.py --inp ult.jsonl --id-key ID --fn-key FN --src-key SRC --n 20 --seed 2026
Commit tasks/tasks.jsonl and selection_log.json. Do not change them after seeing any results.

## 2b. Check your Gemini key and pick the exact model name
    python3 list_models.py
Copy one name exactly into --model. Never paste your key into chats or commit it to git; if it leaks, delete it in AI Studio.

## 3. Pilot (cheap, catches bugs)
    python run_experiment.py --tasks tasks/tasks.jsonl --provider gemini --model <PINNED_MODEL_ID> --thinking-budget 0 --budget 8000 --reps 1 --out pilot.jsonl
Look at pilot.jsonl: do trajectories stop for sensible reasons? Is `init_valid` neither ~0% nor ~100%?
If init_valid is ~100%, repair never triggers: raise difficulty (harder functions) or lower model strength, and re-freeze BEFORE the real run. Do not delete the pilot; mention it in the paper.

## 4. Real run (resumable)
    python run_experiment.py --tasks tasks/tasks.jsonl --provider gemini --model <PINNED_MODEL_ID> --thinking-budget 0 --budget 8000 --reps 3 --out runs.jsonl

## 5. Analyze and fill the paper
    python analyze.py runs.jsonl --latex ../paper/results
Compile paper/main.tex. Tables and numbers fill in automatically. Then:
- [ ] Abstract: add the direction sentence.
- [ ] Discussion: keep ONE of three paragraphs, delete the others and the TODO.
- [ ] Fill remaining \todo{} items (selection counts, repo URL, authors).
- [ ] Send me runs.jsonl + analyze output and I will review the write-up for overclaiming.

## Known limits to disclose (already in the paper)
Own mutation operators, no equivalent-mutant filtering, one model, small N, renaming verified structurally only.
Power: 20 functions detects only large effects. If your advisor agrees, use 40-60 functions.

## Gemini notes
- Key: create one in Google AI Studio, set GEMINI_API_KEY. Free-tier keys hit rate limits (429); the code retries with backoff but a full run may be slow.
- Use `--thinking-budget 0` on models that allow it (e.g. Flash). With thinking on, hidden reasoning tokens eat the 1500-token output cap and are charged to the budget; Gemini 2.5 Pro cannot disable thinking, so if you use it, raise `max_output` in llm.py and the budget, and say so in the paper.
- Pin the exact model string (not an alias like "-latest") and record the date; Google updates models.
- Free-tier data may be used by Google to improve products; prefer a paid key if the tasks are not public code.

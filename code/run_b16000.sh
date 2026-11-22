#!/usr/bin/env bash
# Full experiment, resumable and safe to rerun. Reads the key from .env in this folder (never printed).
# Usage: bash run_all.sh        (set RR_MOCK=1 for a no-API self-test)
set -u
cd "$(dirname "$0")"
set -a; [ -f .env ] && source .env; set +a
if [ "${RR_MOCK:-0}" = "1" ]; then
  ARGS=(--tasks tasks/smoke_tasks.jsonl --mock --reps 1 --out runs_mock.jsonl); OUT=runs_mock.jsonl
else
  [ -n "${NVIDIA_API_KEY:-}" ] || { echo "NVIDIA_API_KEY missing"; exit 1; }
  ARGS=(--tasks tasks/tasks.jsonl --provider openai --model nvidia/nemotron-3.5-lightning-30b-a3b
        --extra-body '{"chat_template_kwargs": {"enable_thinking": false}}' --max-output 1500 --budget 16000 --reps 2 --out runs_b16000.jsonl)
  OUT=runs_b16000.jsonl
fi
touch run_b16000.log
for i in $(seq 1 12); do
  start=$(wc -l < run_b16000.log)
  if python3 run_experiment.py "${ARGS[@]}" >> run_b16000.log 2>&1; then echo "experiment finished"; break; fi
  if tail -n +$((start + 1)) run_b16000.log | grep -qiE "503|UNAVAILABLE|429|RESOURCE_EXHAUSTED|rate limit|timed out|timeout|connection"; then
    echo "attempt $i: transient error at $(date); sleeping 180s"; sleep 180
  else
    echo "NON-TRANSIENT failure; last log lines:"; tail -n 30 run_b16000.log; exit 2
  fi
done
mkdir -p ../paper/results_b16000
python3 analyze.py "$OUT" --latex ../paper/results_b16000 > analysis_output_b16000.txt 2>&1
echo "rows: $(wc -l < "$OUT")"; cat analysis_output_b16000.txt

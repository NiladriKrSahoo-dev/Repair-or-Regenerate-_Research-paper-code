# Untested here. Build: docker build -t rr .   Run (mounts this folder, passes key):
# docker run --rm -it -e ANTHROPIC_API_KEY -v "$PWD":/work -w /work rr python run_experiment.py --tasks tasks/tasks.jsonl --model MODEL --budget 8000 --reps 3
FROM python:3.12-slim
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

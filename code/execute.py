"""Sandboxed-ish execution: subprocess + timeout in a temp dir. Use a container for untrusted code."""
import subprocess, tempfile, os, json, sys, shutil

def run_tests(src, test, timeout=30, cov=False):
    d = tempfile.mkdtemp(prefix="rr_")
    try:
        open(os.path.join(d, "target.py"), "w").write(src)
        open(os.path.join(d, "test_target.py"), "w").write(test)
        cmd = [sys.executable, "-m", "pytest", "-x", "-q", "--no-header", "-p", "no:cacheprovider", "test_target.py"]
        if cov:
            cmd = [sys.executable, "-m", "coverage", "run", "--branch", "--include=target.py", "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "test_target.py"]
        try:
            p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return dict(executable=False, passed=False, timeout=True, output="TIMEOUT", branch_cov=None)
        out = (p.stdout + p.stderr)[-2000:]
        # pytest exit codes: 0 all passed, 1 tests failed, 2/3/4 interrupted/internal/usage (collection errors -> 2), 5 none collected
        r = dict(executable=p.returncode in (0, 1), passed=p.returncode == 0, timeout=False, output=out, branch_cov=None)
        if cov and r["executable"]:
            subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "c.json"], cwd=d, capture_output=True)
            try:
                s = json.load(open(os.path.join(d, "c.json")))["files"]["target.py"]["summary"]
                nb = s.get("num_branches", 0)
                r["branch_cov"] = (s["covered_branches"] / nb) if nb else None
            except Exception:
                pass
        return r
    finally:
        shutil.rmtree(d, ignore_errors=True)

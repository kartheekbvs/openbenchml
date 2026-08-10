"""v2.6 smoke test: verify notebook.py imports cleanly and the new guards work."""
import sys, os
sys.path.insert(0, "/home/z/my-project")

# 1. Module must import without syntax errors
from app.routes import notebook as nb
print("[1] notebook.py imports OK")

# 2. Memory-budget helper exists
rss = nb._server_rss_bytes()
assert rss > 0, "RSS should be > 0 on Linux"
print(f"[2] _server_rss_bytes() = {rss/1024/1024:.1f} MB OK")

# 3. _check_memory_budget() returns None when we're under the limit
err = nb._check_memory_budget()
print(f"[3] _check_memory_budget() = {err!r} (should be None under normal load) OK")

# 4. Reaper constants are right
assert nb.SESSION_TTL_SECONDS == 15 * 60, f"TTL should be 900, got {nb.SESSION_TTL_SECONDS}"
assert nb._MAX_SESSIONS == 12, f"_MAX_SESSIONS should be 12, got {nb._MAX_SESSIONS}"
assert nb._SERVER_RSS_LIMIT_BYTES == 700 * 1024 * 1024
assert nb._MAX_OUTPUT_BYTES == 1 * 1024 * 1024
print(f"[4] constants OK: TTL={nb.SESSION_TTL_SECONDS}s, MAX_SESSIONS={nb._MAX_SESSIONS}, "
      f"RSS_LIMIT={nb._SERVER_RSS_LIMIT_BYTES//1024//1024}MB, OUT_CAP={nb._MAX_OUTPUT_BYTES//1024}KB")

# 5. Reaper starts
sess = nb._get_or_create_session(user_id=999999)
assert nb._reaper_started is True, "Reaper should have started"
print(f"[5] Reaper started OK, session.user_id={sess.user_id}")

# 6. git clone auto-prefix logic
import re
test_cases = [
    ("git clone https://huggingface.co/zai-org/GLM-5.2",
     "git clone --depth 1 --filter=blob:none https://huggingface.co/zai-org/GLM-5.2"),
    ("git clone https://github.com/octocat/Hello-World.git target/",
     "git clone --depth 1 --filter=blob:none https://github.com/octocat/Hello-World.git target/"),
    ("git clone --depth 5 https://example.com/repo",  # should NOT modify
     "git clone --depth 5 https://example.com/repo"),
    ("git clone --filter=blob:none https://example.com/repo",  # should NOT modify
     "git clone --filter=blob:none https://example.com/repo"),
    ("GIT CLONE https://example.com/repo",  # case-insensitive
     "GIT CLONE --depth 1 --filter=blob:none https://example.com/repo"),
]
for inp, expected in test_cases:
    cmd = inp
    if re.match(r'^git\s+clone\s+(?!.*--depth)(?!.*--filter)', cmd, re.IGNORECASE):
        cmd = re.sub(r'^(git\s+clone\s+)', r'\1--depth 1 --filter=blob:none ',
                     cmd, count=1, flags=re.IGNORECASE)
    assert cmd == expected, f"FAIL: {inp!r}\n  got:      {cmd!r}\n  expected: {expected!r}"
    print(f"[6] {inp!r} -> {cmd!r} OK")

# 7. run_code output truncation
from app.services.code_runner_service import run_code
result = run_code("print('x' * 5_000_000)")  # 5MB print
assert len(result["stdout"]) < 2_000_000, f"stdout should be truncated, got {len(result['stdout'])} bytes"
assert "truncated at 1 MB" in result["stdout"], "should contain truncation marker"
print(f"[7] stdout truncated to {len(result['stdout'])} bytes (was 5MB) OK")

print("\n=== All v2.6 smoke tests passed ===")

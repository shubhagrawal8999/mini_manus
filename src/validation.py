import ast
import subprocess
import tempfile

def validate_generated_code(code_str: str, language: str = "python") -> tuple[bool, str]:
    """Returns (is_valid, error_message)"""
    if language != "python":
        return True, "Non‑Python code not validated"
    
    # 1. Syntax check
    try:
        ast.parse(code_str)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    
    # 2. Sandbox compile check (no execution of dangerous code)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code_str)
        f.flush()
        result = subprocess.run(
            ["python", "-m", "py_compile", f.name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return False, result.stderr
    
    # 3. Optional: run unit tests if present (simplified)
    if "def test_" in code_str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py") as f2:
            f2.write(code_str + "\n\nif __name__ == '__main__': import pytest; pytest.main()")
            f2.flush()
            test_result = subprocess.run(
                ["python", f2.name],
                capture_output=True, text=True, timeout=10
            )
            if test_result.returncode != 0:
                return False, f"Tests failed:\n{test_result.stderr}"
    
    return True, "OK"

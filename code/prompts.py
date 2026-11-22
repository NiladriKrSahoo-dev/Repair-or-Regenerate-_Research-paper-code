GEN = """You are writing pytest unit tests for the Python function `{fn}`.
The code is in a module named `target`; import it with `from target import {fn}`.
Return ONE complete pytest file in a single ```python code block. The tests will run on Python 3.9: do not use `X | Y` type unions, `match` statements, or any other syntax newer than Python 3.9.

```python
{src}
```"""

REPAIR = """You are fixing a pytest file for the Python function `{fn}` (module `target`).
Function under test:
```python
{src}
```
Previous test file:
```python
{prev}
```
Result of running it:
```
{diag}
```
Return the corrected complete pytest file in a single ```python code block. The tests will run on Python 3.9: do not use `X | Y` type unions, `match` statements, or any other syntax newer than Python 3.9."""

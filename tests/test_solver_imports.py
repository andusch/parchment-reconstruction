"""Import graph of the solvers, not a source-text ban.

``segment``, ``edge_chord``, ``pairwise_join``, ``join_rank``, and ``scale``
must not reach the benchmark generator or the recall writers. The walk
follows import opcodes, including an import nested in a function and an
import that exists only in a helper those modules load. Renaming a string
in a solver file does not drop that edge. A fresh interpreter then imports
each solver and records every module the import system loads.
"""

import json
import subprocess
import sys
from modulefinder import ModuleFinder

_SOLVERS = (
    "prw.segment",
    "prw.edge_chord",
    "prw.pairwise_join",
    "prw.join_rank",
    "prw.scale",
)
_BANNED = (
    "prw.synthetic_tear",
    "prw.join_recall",
    "prw.outline_agreement",
)
_RUNTIME_IMPORTS = """
import importlib
import json
import sys

banned = sys.argv[2:]
solver = sys.argv[1]


class _Trace:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def find_spec(self, fullname: str, path: object, target: object = None) -> None:
        self.seen.append(fullname)
        return None


trace = _Trace()
sys.meta_path.insert(0, trace)
importlib.import_module(solver)
loaded = set(sys.modules) | set(trace.seen)
found = sorted(
    name
    for name in loaded
    if name in banned or any(name.startswith(item + ".") for item in banned)
)
print(json.dumps(found))
"""


def _banned(names: set[str]) -> list[str]:
    return sorted(
        name
        for name in names
        if name in _BANNED or any(name.startswith(f"{banned}.") for banned in _BANNED)
    )


def _import_graph(module_name: str) -> set[str]:
    finder = ModuleFinder()
    finder.import_hook(module_name)
    if module_name not in finder.modules:
        raise AssertionError(f"{module_name} was not loaded by the import walk.")
    return set(finder.modules)


def test_solver_import_graph_excludes_the_generator_and_recall_writers() -> None:
    for module_name in _SOLVERS:
        banned = _banned(_import_graph(module_name))
        assert not banned, f"{module_name} import graph reaches {banned}"
        completed = subprocess.run(
            [sys.executable, "-c", _RUNTIME_IMPORTS, module_name, *_BANNED],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        loaded = json.loads(completed.stdout)
        assert loaded == [], f"{module_name} loaded {loaded}"

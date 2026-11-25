from functools import cache
from importlib.util import find_spec

from ast_grep_py import register_dynamic_language


@cache
def ensure_dockerfile_language():
    try:
        binding = find_spec("tree_sitter_dockerfile._binding")
    except ModuleNotFoundError:
        binding = None
    if binding is None or binding.origin is None:
        raise ValueError("Dockerfile changes require the Dockerfile grammar. "
                         "Prebuilt support is available on Apple Silicon and x86-64 Linux.")
    register_dynamic_language({"dockerfile": {
        "library_path": binding.origin,
        "language_symbol": "tree_sitter_dockerfile",
        "extensions": ["dockerfile"],
    }})

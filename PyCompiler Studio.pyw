"""Start PyCompiler Studio WITHOUT a console window (double-click this file)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pycompiler_studio import main  # noqa: E402

if __name__ == "__main__":
    main()

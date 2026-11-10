import os
import sys
import tempfile

# Settings and logs go to a throwaway folder, and nothing is printed, before
# any Evictarr module is imported
os.environ["CONFIG_DIR"] = tempfile.mkdtemp(prefix="evictarr-tests-")
os.environ["LOG_OUTPUT"] = "file"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

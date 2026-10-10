from fnmatch import fnmatchcase


def match_file(path: str, extensions: list, names: list):
    """Return what a file matched (".rar" or the name pattern), or None.

    Extensions may use wildcards ("r[0-9][0-9]" for .r00 to .r99). Name patterns
    are wildcards matched against the file name, or against its path inside the
    download if the pattern contains "/", ignoring case: "*sample*" or "*/extras/*".
    """
    path = path.replace("\\", "/").lower()
    name = path.rsplit("/", 1)[-1]

    for ext in extensions:
        if fnmatchcase(name, f"*.{ext}"):
            # Report the real extension for wildcards, e.g. ".r01" not ".r[0-9][0-9]"
            return "." + name.rsplit(".", 1)[-1] if any(c in ext for c in "*?[") else f".{ext}"

    # Patterns without a "/" only look at the file name, so a release folder
    # that happens to contain the word (e.g. a show called "Sample") can't match
    for pattern in names:
        if fnmatchcase(path if "/" in pattern else name, pattern):
            return pattern

    return None

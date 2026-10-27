import os
import shutil
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


def skip_reason(path: str, all_files: list):
    """Why a file shouldn't be downloaded, or None. all_files is every file name in the download.

    Covers the skip list (SKIPPED_EXTENSIONS/NAMES), samples, and subtitle or extra
    audio files that aren't in one of my languages.
    """
    import utils.config as config
    from utils import languages as lang

    if match := match_file(path, config.skipped_extensions, config.skipped_names):
        return match

    if config.skip_samples and lang.is_sample(path):
        return "sample"

    if config.skip_other_languages:
        _, _, ext = lang.split_name(path)
        is_subtitle = ext in lang.SUBTITLE_EXTENSIONS
        # Audio files only count as extra tracks next to a video, so music isn't touched
        is_extra_audio = ext in lang.AUDIO_EXTENSIONS and any(
            lang.split_name(f)[2] in lang.VIDEO_EXTENSIONS for f in all_files
        )
        if is_subtitle or is_extra_audio:
            found = lang.file_languages(path)
            kind = "subtitle" if is_subtitle else "audio"
            if not found and not config.keep_unlabelled_languages:
                return f"{kind} in an unknown language"
            if found and not (found & config.language_codes):
                names = ", ".join(sorted(lang.LANGUAGES[c][0] for c in found))
                return f"{kind} in {names}"
    return None


def release_language_problem(name: str):
    """Why a release should be rejected for its language, or None."""
    import utils.config as config
    from utils import languages as lang

    if not config.reject_other_language_releases:
        return None
    found, multi = lang.release_languages(name)
    if not found or multi or found & config.language_codes:
        return None
    names = ", ".join(sorted(lang.LANGUAGES[c][0] for c in found))
    return f"release is in {names}"


# Suffixes download clients add to files still being downloaded
PARTIAL_SUFFIXES = (".!qb", ".part", ".!ut", ".incomplete")


def download_key(name: str) -> str:
    """A name to compare a file or folder on disk with a download's name."""
    name = name.lower()
    for suffix in PARTIAL_SUFFIXES:
        name = name.removesuffix(suffix)
    return name


def _newest_change(path: str) -> float:
    newest = os.lstat(path).st_mtime
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                newest = max(newest, os.lstat(os.path.join(root, name)).st_mtime)
            except OSError:
                pass
    return newest


def _holds_downloads(path: str, known: set, folders: set, depth: int) -> bool:
    """Whether a folder holds a download somewhere inside (a category folder like tv-sonarr)."""
    if depth == 0:
        return False
    try:
        entries = list(os.scandir(path))
    except OSError:
        return True  # can't look inside, so leave it alone
    for entry in entries:
        key = download_key(entry.name)
        if key in known:
            return True
        if entry.is_dir(follow_symlinks=False) and (
            key in folders or _holds_downloads(entry.path, known, folders, depth - 1)
        ):
            return True
    return False


def find_leftovers(folder: str, known: set, folders: set, changed_before: float, depth: int = 4) -> list:
    """Files and folders in folder that don't belong to any download.

    known is every download's name (from download_key). A folder named after a
    category in folders, or one holding a download, is looked inside instead of
    being counted, so category folders are never taken for leftovers. Hidden
    entries, empty folders and anything changed after changed_before are left alone.
    """
    leftovers = []
    for entry in sorted(os.scandir(folder), key=lambda e: e.name):
        key = download_key(entry.name)
        if entry.name.startswith(".") or key in known:
            continue
        if entry.is_dir(follow_symlinks=False) and (
            key in folders or _holds_downloads(entry.path, known, folders, depth)
        ):
            if depth > 0:
                leftovers += find_leftovers(entry.path, known, folders, changed_before, depth - 1)
            continue
        try:
            # An empty folder takes no space, and may be one the client expects, such as its incomplete folder
            if entry.is_dir(follow_symlinks=False) and not any(os.scandir(entry.path)):
                continue
            if _newest_change(entry.path) > changed_before:
                continue
        except OSError:
            continue
        leftovers.append(entry.path)
    return leftovers


def size_of(path: str) -> int:
    if not os.path.isdir(path) or os.path.islink(path):
        return os.lstat(path).st_size
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def remove_path(path: str):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)

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

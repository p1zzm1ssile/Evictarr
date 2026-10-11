"""Working out languages from file and release names.

Evictarr only sees names, not what's inside files, so this reads the language
tags people put in names: "Movie.2024.en.srt", "Subs/3_English.srt",
"Movie.ger.dts", or "Show.S01E01.GERMAN.1080p" for a whole release.
"""

import re

# code: (name, tags found in file names). Two-letter tags are only trusted at the
# end of a file name (see file_languages), since "it" or "no" can be a title word.
LANGUAGES = {
    "en": ("English", {"en", "eng", "english"}),
    "fr": ("French", {"fr", "fre", "fra", "french", "francais", "vff", "vfq", "truefrench"}),
    "de": ("German", {"de", "ger", "deu", "german", "deutsch"}),
    "es": ("Spanish", {"es", "spa", "spanish", "espanol", "castellano", "latino"}),
    "it": ("Italian", {"it", "ita", "italian", "italiano"}),
    "pt": ("Portuguese", {"pt", "por", "portuguese", "portugues", "brazilian", "ptbr"}),
    "nl": ("Dutch", {"nl", "dut", "nld", "dutch", "nederlands", "flemish"}),
    "ru": ("Russian", {"ru", "rus", "russian"}),
    "pl": ("Polish", {"pl", "pol", "polish", "polski"}),
    "sv": ("Swedish", {"sv", "swe", "swedish", "svenska"}),
    "da": ("Danish", {"da", "dan", "danish", "dansk"}),
    "nb": ("Norwegian", {"nb", "nor", "nob", "norwegian", "norsk"}),
    "fi": ("Finnish", {"fi", "fin", "finnish", "suomi"}),
    "ja": ("Japanese", {"ja", "jp", "jpn", "japanese"}),
    "zh": ("Chinese", {"zh", "chi", "zho", "chs", "cht", "chinese", "mandarin", "cantonese"}),
    "ko": ("Korean", {"ko", "kor", "korean"}),
    "hi": ("Hindi", {"hin", "hindi"}),  # "hi" usually means hearing impaired
    "ar": ("Arabic", {"ar", "ara", "arabic"}),
    "tr": ("Turkish", {"tr", "tur", "turkish"}),
    "el": ("Greek", {"el", "gre", "ell", "greek"}),
    "he": ("Hebrew", {"he", "heb", "hebrew"}),
    "cs": ("Czech", {"cs", "cze", "ces", "czech"}),
    "hu": ("Hungarian", {"hu", "hun", "hungarian", "magyar"}),
    "ro": ("Romanian", {"ro", "rum", "ron", "romanian"}),
    "uk": ("Ukrainian", {"uk", "ukr", "ukrainian"}),
    "th": ("Thai", {"th", "tha", "thai"}),
    "vi": ("Vietnamese", {"vi", "vie", "vietnamese"}),
    "id": ("Indonesian", {"id", "ind", "indonesian"}),
}

# Words that sit next to a language tag in subtitle names without being one
MODIFIERS = {"forced", "sdh", "cc", "hi", "default", "full", "sub", "subs", "subtitle", "subtitles",
             "signs", "songs", "dub", "dubbed", "track", "audio", "commentary",
             # regions, as in pt-BR or es-MX
             "br", "pt", "mx", "latam", "la", "us", "gb", "au", "ca", "tw", "hk", "cn", "eu"}

# Release-name tags meaning "this release has several languages"
MULTI_TAGS = {"multi", "dual", "multisubs"}

SUBTITLE_EXTENSIONS = {"srt", "ass", "ssa", "sub", "idx", "sup", "vtt", "smi", "ttml"}
AUDIO_EXTENSIONS = {"mka", "ac3", "eac3", "dts", "dtshd", "thd", "aac", "flac", "mp3", "ogg", "opus", "m4a", "wav"}
VIDEO_EXTENSIONS = {"mkv", "mp4", "avi", "m4v", "ts", "m2ts", "wmv", "mov", "webm", "mpg", "mpeg"}

_TAG_TO_LANGUAGE = {tag: code for code, (_, tags) in LANGUAGES.items() for tag in tags}


def _tokens(text):
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def split_name(path):
    """(folders, file name without extension, extension), all lower case."""
    parts = path.replace("\\", "/").lower().split("/")
    name = parts[-1]
    stem, _, ext = name.rpartition(".")
    if not stem:
        stem, ext = name, ""
    return parts[:-1], stem, ext


def file_languages(path):
    """The languages a subtitle or audio file's name says it's in.

    Tags are read from the end of the name backwards ("Movie.2014.en.forced.srt"),
    stopping at the first word that isn't a language or a modifier, so a title
    word like "It" in "It.Follows.2014.srt" isn't read as Italian. Full language
    names count anywhere in the file name ("Subs/3_English.srt").
    """
    folders, stem, _ = split_name(path)
    found = set()
    for token in reversed(_tokens(stem)):
        if token in _TAG_TO_LANGUAGE:
            found.add(_TAG_TO_LANGUAGE[token])
        elif token in MODIFIERS or (token.isdigit() and len(token) <= 2):
            continue  # "forced", "sdh", or a track number like the 3 in "3_English"
        else:
            break
    for token in _tokens(stem):
        code = _TAG_TO_LANGUAGE.get(token)
        if code and len(token) > 3:
            found.add(code)
    return found


# Where the title ends in a release name: a year, a season/episode or a resolution
_TITLE_END = re.compile(r"^((19|20)\d\d|s\d{1,3}(e\d{1,4})*|\d{3,4}p|\d{1,2}x\d{2,3})$")


def release_languages(name):
    """Language tags in a release name, and whether it's tagged as multi-language.

    Only words after the title count (after the year, season/episode or
    resolution), so "Italian.Job.2003" or "The.German.2006" aren't read as
    foreign releases. Two-letter tags are ignored, since they're too often words.
    """
    tokens = _tokens(name)
    end = next((i for i, t in enumerate(tokens) if _TITLE_END.match(t)), None)
    if end is None:
        return set(), False
    after = tokens[end + 1:]
    found = {_TAG_TO_LANGUAGE[t] for t in after if t in _TAG_TO_LANGUAGE and len(t) >= 3}
    return found, bool(set(after) & MULTI_TAGS)


def is_sample(path):
    folders, stem, ext = split_name(path)
    return ext in VIDEO_EXTENSIONS and ("sample" in _tokens(stem) or any(f in ("sample", "samples") for f in folders))

import os
import time

from utils.files import download_key, find_leftovers, looks_like_download, match_file

MALWARE = ["arj", "lnk", "exe", "bat", "cmd", "com", "scr", "pif", "vbs", "ps1"]


def test_blocked_extension_matches_the_file_name():
    assert match_file("Movie.2024.1080p/setup.exe", MALWARE, []) == ".exe"
    assert match_file("Movie.2024.1080p\\SETUP.EXE", MALWARE, []) == ".exe"
    assert match_file("Movie.2024.1080p/movie.mkv", MALWARE, []) is None


def test_wildcard_extension_reports_the_real_one():
    assert match_file("Show.S01/show.r07", ["r[0-9][0-9]"], []) == ".r07"


def test_name_pattern_without_a_slash_ignores_the_folder():
    assert match_file("Sample.Show.S01E01/episode.mkv", [], ["*sample*"]) is None
    assert match_file("Show.S01E01/sample.mkv", [], ["*sample*"]) == "*sample*"
    assert match_file("Show.S01E01/extras/bonus.mkv", [], ["*/extras/*"]) == "*/extras/*"


def test_download_key_ignores_case_and_partial_suffixes():
    assert download_key("Movie.2024.1080p.mkv.!qB") == "movie.2024.1080p.mkv"
    assert download_key("Show.S01E01.part") == "show.s01e01"


def test_only_release_names_look_like_downloads():
    assert looks_like_download("Indiana.Jones.1981.2160p.BDRip")
    assert looks_like_download("Show.S01E05.WEB-DL")
    assert not looks_like_download("movertest")
    assert not looks_like_download("backup")


def make(path, age_minutes=600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("x")
    old = time.time() - age_minutes * 60
    os.utime(path, (old, old))


def test_find_leftovers(tmp_path):
    root = str(tmp_path)
    make(f"{root}/tv-sonarr/Known.Show.S01E01.1080p/ep.mkv")
    make(f"{root}/tv-sonarr/Gone.Show.S02E03.1080p/ep.mkv")
    make(f"{root}/Old.Movie.2001.1080p.mkv")
    make(f"{root}/New.Movie.2025.1080p.mkv", age_minutes=1)
    make(f"{root}/movertest/file.txt")
    make(f"{root}/.hidden/file")
    os.makedirs(f"{root}/incomplete")
    # Making the files changed their folders, so age the folders too
    old = time.time() - 600 * 60
    for folder in ("tv-sonarr/Known.Show.S01E01.1080p", "tv-sonarr/Gone.Show.S02E03.1080p", "movertest"):
        os.utime(f"{root}/{folder}", (old, old))

    found = find_leftovers(root, {"known.show.s01e01.1080p"}, {"tv-sonarr"}, time.time() - 3600)

    assert sorted(os.path.relpath(p, root) for p in found) == [
        "Old.Movie.2001.1080p.mkv",
        os.path.join("tv-sonarr", "Gone.Show.S02E03.1080p"),
    ]

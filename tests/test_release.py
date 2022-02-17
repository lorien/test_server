import re

from test_server import __version__


def test_changelog():
    """Check release records in chenge log.

    Parse changelog and ensure that it contains
    * unreleased version younger than release date
    * release version has a date
    """
    re_date = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    ver_dates = {}
    ver_history = []
    for line in open("CHANGELOG.md", encoding="utf-8"):
        if line.startswith("## ["):
            ver = line.split("[")[1].split("]")[0]
            date = line.split("-", 1)[1].strip().lower()
            ver_dates[ver] = date
            ver_history.append(ver)
    release = __version__
    assert "unreleased" not in ver_dates[release]
    assert re_date.match(ver_dates[release])
    assert ver_history.index(release) == 1

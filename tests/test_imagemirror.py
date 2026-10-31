import subprocess
import sys

import pytest

from imagemirror.mirror import Image, copy_plan, parse, pull_plan

CATALOGUE = """
# Images the CI of vladpetl-dev repositories pulls.
postgres:18
testcontainers/ryuk:0.14.0   # Testcontainers' reaper
"""


def test_a_catalogue_lists_images_with_comments_and_blank_lines():
    assert parse(CATALOGUE) == [Image("postgres", "18"), Image("testcontainers/ryuk", "0.14.0")]


@pytest.mark.parametrize(
    "line, reason",
    [
        ("postgres", "needs a tag"),
        ("postgres:latest", "moving 'latest'"),
        ("Postgres:18", "lower case"),
        ("ghcr.io/x/postgres:18", "Docker Hub name"),
        ("public.ecr.aws/docker/library/postgres:18", "Docker Hub name"),
        ("postgres@sha256:abc", "needs a tag"),
        ("postgres:18 extra", "one image per line"),
    ],
)
def test_bad_entries_are_refused_with_the_line(line, reason):
    with pytest.raises(ValueError) as error:
        parse(f"# head\n{line}\n")
    assert "line 2" in str(error.value)
    assert reason in str(error.value)


def test_duplicates_are_refused():
    with pytest.raises(ValueError, match="twice"):
        parse("postgres:18\npostgres:18\n")


def test_copy_plan_names_the_mirror_target_and_the_sources_in_order():
    plan = copy_plan(parse(CATALOGUE), "ghcr.io/vladpetl-dev/mirror/")

    assert plan == [
        (
            "ghcr.io/vladpetl-dev/mirror/postgres:18",
            ["docker.io/library/postgres:18", "public.ecr.aws/docker/library/postgres:18"],
        ),
        (
            "ghcr.io/vladpetl-dev/mirror/testcontainers/ryuk:0.14.0",
            ["docker.io/testcontainers/ryuk:0.14.0"],
        ),
    ]


def test_pull_plan_maps_each_image_to_its_mirror_or_to_none():
    images = parse("postgres:18 testcontainers/ryuk:0.14.0".replace(" ", "\n"))

    assert pull_plan(images, "ghcr.io/vladpetl-dev/mirror") == [
        ("postgres:18", "ghcr.io/vladpetl-dev/mirror/postgres:18"),
        ("testcontainers/ryuk:0.14.0", "ghcr.io/vladpetl-dev/mirror/testcontainers/ryuk:0.14.0"),
    ]
    assert pull_plan(images, "") == [("postgres:18", None), ("testcontainers/ryuk:0.14.0", None)]


@pytest.mark.parametrize(
    "mirror", ["ghcr.io/Owner/m", "ghcr.io", "https://ghcr.io/x", "ghcr.io/x y"]
)
def test_a_malformed_mirror_is_refused(mirror):
    with pytest.raises(ValueError, match="mirror"):
        pull_plan([Image("postgres", "18")], mirror)


def run(*args, stdin=""):
    return subprocess.run(
        [sys.executable, "-m", "imagemirror", *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_prints_tab_separated_plans(tmp_path):
    catalogue = tmp_path / "images.txt"
    catalogue.write_text(CATALOGUE)

    copy = run("copy-plan", str(catalogue), "--mirror", "ghcr.io/vladpetl-dev/mirror")
    pull = run("pull-plan", "--mirror", "", stdin="postgres:18\n testcontainers/ryuk:0.14.0 ")

    assert copy.returncode == 0
    assert copy.stdout.splitlines()[0] == (
        "ghcr.io/vladpetl-dev/mirror/postgres:18\t"
        "docker.io/library/postgres:18\tpublic.ecr.aws/docker/library/postgres:18"
    )
    assert pull.stdout.splitlines() == ["postgres:18\t", "testcontainers/ryuk:0.14.0\t"]


def test_cli_fails_readably_on_a_bad_list():
    result = run("pull-plan", "--mirror", "ghcr.io/vladpetl-dev/mirror", stdin="postgres\n")

    assert result.returncode == 2
    assert "needs a tag" in result.stderr


def test_the_repository_catalogue_is_valid():
    with open("images.txt") as f:
        assert parse(f.read())

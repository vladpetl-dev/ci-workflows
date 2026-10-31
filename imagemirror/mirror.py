"""Plans for mirroring Docker Hub images to a registry we control, and for pulling them in CI.

The catalogue (`images.txt`) names images as Docker Hub does (`postgres:18`,
`testcontainers/ryuk:0.14.0`), one per line; `#` starts a comment. Each image is copied to
`<mirror>/<name>:<tag>`. CI pulls the mirror copy and tags it with the Docker Hub name, so tests
keep using plain names and never depend on the mirror.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A Docker Hub repository: optional namespace, lower-case path components; a tag is required.
_NAME = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)?")
_TAG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
_MIRROR = re.compile(r"[a-z0-9.-]+\.[a-z]{2,}(?::\d+)?(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+")
_ECR_PUBLIC = "public.ecr.aws/docker/library"


@dataclass(frozen=True)
class Image:
    name: str
    tag: str

    @property
    def ref(self) -> str:
        return f"{self.name}:{self.tag}"

    @property
    def official(self) -> bool:
        """Docker official images have no namespace (`postgres`), stored as `library/postgres`."""
        return "/" not in self.name


def _image(entry: str, where: str) -> Image:
    if " " in entry.strip() or "\t" in entry.strip():
        raise ValueError(f"{where}: one image per line: '{entry.strip()}'")
    name, sep, tag = entry.strip().rpartition(":")
    if not sep or "@" in entry or "/" in tag:
        raise ValueError(f"{where}: '{entry.strip()}' needs a tag (name:tag)")
    if "." in name.split("/")[0] or name.count("/") > 1:
        raise ValueError(
            f"{where}: '{entry.strip()}' must be a Docker Hub name such as postgres:18"
        )
    if name != name.lower():
        raise ValueError(f"{where}: '{entry.strip()}' must be lower case")
    if not _NAME.fullmatch(name) or not _TAG.fullmatch(tag):
        raise ValueError(f"{where}: '{entry.strip()}' is not a valid image name")
    if tag == "latest":
        raise ValueError(f"{where}: '{entry.strip()}' uses the moving 'latest' tag; pin a version")
    return Image(name, tag)


def parse(text: str) -> list[Image]:
    """Images from a catalogue or a CI input: one per line, `#` comments allowed."""
    images: list[Image] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        entry = raw.split("#", 1)[0].strip()
        if not entry:
            continue
        image = _image(entry, f"line {number}")
        if image in images:
            raise ValueError(f"line {number}: {image.ref} is listed twice")
        images.append(image)
    return images


def _mirror(mirror: str) -> str:
    mirror = mirror.strip().rstrip("/")
    if not _MIRROR.fullmatch(mirror):
        raise ValueError(
            f"image mirror must look like ghcr.io/<owner>/<path> in lower case: '{mirror}'"
        )
    return mirror


def copy_plan(images: list[Image], mirror: str) -> list[tuple[str, list[str]]]:
    """Per image: the mirror target and the sources to copy it from, in the order to try."""
    base = _mirror(mirror)
    plan = []
    for image in images:
        hub = f"docker.io/{'library/' if image.official else ''}{image.ref}"
        sources = [hub] + ([f"{_ECR_PUBLIC}/{image.ref}"] if image.official else [])
        plan.append((f"{base}/{image.ref}", sources))
    return plan


def pull_plan(images: list[Image], mirror: str) -> list[tuple[str, str | None]]:
    """Per image: its Docker Hub name and its mirror copy (None when no mirror is used)."""
    base = _mirror(mirror) if mirror.strip() else None
    return [(image.ref, f"{base}/{image.ref}" if base else None) for image in images]

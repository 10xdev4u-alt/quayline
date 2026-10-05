"""Issue 226: the Dockerfile's base images are pinned by digest, and it is a test not a habit.

`Dockerfile` pins `python:3.13-slim-bookworm` by digest because a CodeRabbit review caught a
floating tag. The reasoning next to it is right: a floating tag means a rebuild months from
now produces a different base, and "it worked when we wrote it" becomes untestable.

Nothing held that in place. Rewriting the line to drop the digest passes every test in this
repository, and the failure would not surface until someone rebuilt months later and found a
different Python patch release underneath the same tag. That is the shape of the bug this
file exists to close: a control whose only enforcement is that somebody remembered.

The test reads the Dockerfile as text and asserts the pin. No network, no Docker, no build,
so it runs in the ordinary suite and cannot rot into something that only passes in CI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parent.parent / "Dockerfile"

#: A ``FROM`` that names an image, either the runtime stage or the build stage.
FROM_LINE = re.compile(r"^FROM\s+(?P<image>\S+)", re.MULTILINE)

#: One word describing where the image comes from. These are not registry pulls and have no
#: digest to pin, so requiring one would be requiring a meaningless value.
LOCAL_SOURCES = frozenset({"scratch", "base", "build"})


def _from_images() -> list[str]:
    return [
        match.group("image")
        for match in FROM_LINE.finditer(DOCKERFILE.read_text())
        if match.group("image").split("/")[-1].split(":")[0] not in LOCAL_SOURCES
    ]


def test_the_dockerfile_exists() -> None:
    """Fails loudly and specifically if this file is ever pointed at the wrong path.

    Without it, every other test here would pass vacuously on an empty list, which is the
    failure mode the "proved it fails" step in the issue was checking for.
    """
    assert DOCKERFILE.is_file(), f"no Dockerfile at {DOCKERFILE}"


def test_the_dockerfile_has_at_least_one_registry_image() -> None:
    """Guards the guard. An empty parse must fail here rather than pass every pin check."""
    assert _from_images(), "found no registry FROM lines; the regex is wrong"


def test_every_registry_image_is_pinned_by_digest() -> None:
    """The invariant.

    A floating tag is the failure. The digest is what makes a rebuild months from now
    reproducible, and reproducibility of the *base* is what the reproducibility claim in
    `docs/SELFHOST.md` rests on.
    """
    unpinned = [image for image in _from_images() if "@sha256:" not in image]

    assert not unpinned, (
        "these FROM lines pull a floating tag:\n"
        + "\n".join(f"  {image}" for image in unpinned)
        + "\n\nA rebuild months from now gets a different base, and 'it worked when we wrote"
        " it' becomes untestable. Pin with @sha256: from"
        " `docker buildx imagetools inspect <image>`."
    )


@pytest.mark.parametrize("image", _from_images())
def test_the_pinned_digest_is_a_full_length_sha256(image: str) -> None:
    """A truncated digest is a prefix, not a pin.

    `sha256:5024f48` would match many images over the life of the tag. The value is 64 hex
    characters and this asserts the shape rather than the value, so the test survives a
    deliberate re-pin.
    """
    if "@" not in image:
        # Absence is `test_every_registry_image_is_pinned_by_digest`'s job, and it reports it
        # far better than this test can. Indexing a missing `@` here raised IndexError and
        # buried the real message under a traceback.
        pytest.skip(f"{image} carries no digest at all")

    digest = image.rsplit("@", 1)[1]
    algo, _, value = digest.partition(":")

    assert algo == "sha256", f"{image} is pinned with {algo}"
    assert len(value) == 64, f"{image} has a {len(value)}-character digest, not 64"
    assert set(value) <= set("0123456789abcdef"), f"{image} digest is not lowercase hex"

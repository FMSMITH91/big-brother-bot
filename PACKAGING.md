BigBrotherBot (B3) packaging
============================

Every release on GitHub has three downloads, all built by the `release` workflow
(`.github/workflows/release.yml`):

  - `b3-<version>-py3-none-any.whl`: the Python wheel (`pip install b3-<version>-py3-none-any.whl`, then run `b3_run`)
  - `b3-<version>.tar.gz`: the source package
  - `b3-<version>-win64-setup.exe`: the Windows installer. It contains its own Python (the official embeddable
    Python from python.org) with B3 and its libraries installed, so users do not need to install Python.

# Making a release

1. Make sure master is green and the CHANGELOG is up to date.
2. Tag the commit and push the tag:

        git tag v2.0.0
        git push origin v2.0.0

   The workflow sets the version from the tag (`scripts/set_version.py`), builds the wheel and source package,
   checks that the wheel contains every B3 file, installs it in a clean environment, builds the Windows installer,
   installs that silently on a Windows machine and runs B3 from it, then creates the GitHub release with the
   three files and generated release notes.

Version numbers follow the scheme the B3 update check understands: `2.0.0`, or `2.0.0a1` / `2.0.0b1` for
pre-releases (`rc` is not part of it). A tag with `a`, `b` or `dev` is published as a GitHub pre-release, which
the update check only offers on the beta channel.

To also record the version in the repository, run `python scripts/set_version.py 2.0.0` and merge that change
before tagging.

# Building locally

Python packages (any platform):

    pip install -r build-requirements.txt
    python -m build

(The workflow installs exact, hash-checked versions of build and setuptools from `.github/ci-requirements.txt` and
builds with `--no-isolation`.)

    python scripts/check_dist.py dist/b3-*.whl

Windows installer (on Windows, with Python 3.14 and [Inno Setup 6](https://jrsoftware.org/isinfo.php)):

    python installer/windows/build_installer.py dist/b3-<version>-py3-none-any.whl --version <version>

The embeddable Python version and its SHA-256 are pinned in `installer/windows/build_installer.py`
(`EMBED_VERSION`, `EMBED_SHA256`); when changing it, update the Python version of the `windows-installer` job in
the workflow to the same minor version.

Pull requests that change the packaging run the same builds and tests, without publishing anything; the built
files can be downloaded from the workflow run's artifacts.

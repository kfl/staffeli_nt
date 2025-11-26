# Nix Setup

This repository includes Nix support via `flake.nix` using
[uv2nix](https://github.com/pyproject-nix/uv2nix) to automatically
sync with `pyproject.toml` and `uv.lock`.

## Usage

### For flake users

```sh
nix develop
```

### For non-flake users

```sh
nix-shell
```

Both methods will provide a development environment with:
- All dependencies from `pyproject.toml` (including dev dependencies and python)
- The `staffeli` command available
- `uv` for package management

## How it works

`flake.lock` is committed to the repository and automatically updated
via GitHub Actions when Python dependencies change. Contributors don't
need to manually run `nix flake lock` unless they're modifying the Nix
configuration itself.

### Updating Nix dependencies

To update nixpkgs, uv2nix, or pyproject-nix versions:

```sh
nix flake update
```

Then test the changes and submit a pull request with the updated `flake.lock`.

**Note:** Only update when there's a specific reason (bug fix, needed feature,
security update, etc.). The PR should explain why the update is necessary.

The `shell.nix` file uses
[flake-compat](https://github.com/edolstra/flake-compat) to provide
backwards compatibility for non-flake users.

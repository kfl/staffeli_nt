# Nix Setup

This repository includes Nix support via `flake.nix` using
[uv2nix](https://github.com/pyproject-nix/uv2nix) to automatically
sync with `pyproject.toml` and `uv.lock`.

## First-time Setup

After cloning the repository, generate the `flake.lock`:

```sh
nix flake lock
```

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

The `flake.nix` uses uv2nix to read from `pyproject.toml` and
`uv.lock`, ensuring the Nix environment stays in sync with the project
dependencies automatically. When you update dependencies via `uv`,
just run `nix flake lock` again to update the Nix environment.

The `shell.nix` file uses
[flake-compat](https://github.com/edolstra/flake-compat) to provide
backwards compatibility for non-flake users.

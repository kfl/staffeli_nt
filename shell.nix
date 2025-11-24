# NOTE: This shell.nix is outdated (uses Python 3.13 and old dependencies).
# It will probably be replaced with flake.nix using uv2nix for automatic sync
# with pyproject.toml and uv.lock. For now, please use 'uv sync' instead for
# the correct Python 3.14 environment. See: https://github.com/kfl/staffeli_nt/issues/72

{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    nativeBuildInputs = [
      (pkgs.python313.withPackages(ps: with ps; [
        ruamel-yaml
        (
          buildPythonPackage rec {
            pname = "canvasapi";
            version = "2.2.0";
            src = fetchPypi {
              inherit pname version;
              sha256 = "sha256-UIfbdzysnZL09GCbPBYNvuzrY2gBQhgIr+4tQ4vEP2I=";
            };
            doCheck = false;
            pyproject = true;
            build-system = [ setuptools ];
            propagatedBuildInputs = [
              ps.pytz
              ps.requests
            ];
          }
        )
      ]))
    ];
}

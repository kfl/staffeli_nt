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

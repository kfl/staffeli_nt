{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    nativeBuildInputs = [
      (pkgs.python39.withPackages(ps: with ps; [
        ruamel-yaml 
        (
          buildPythonPackage rec {
            pname = "canvasapi";
            version = "2.2.0";
            src = fetchPypi {
              inherit pname version;
              sha256 = "5087db773cac9d92f4f4609b3c160dbeeceb636801421808afee2d438bc43f62";
            };
            doCheck = false;
            propagatedBuildInputs = [
              pkgs.python39Packages.pytz
              pkgs.python39Packages.requests
            ];
          }
        )
      ]))
    ];
}

{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    nativeBuildInputs = [
      (pkgs.python310.withPackages(ps: with ps; [
        ruamel-yaml 
        (
          buildPythonPackage rec {
            pname = "canvasapi";
            version = "3.2.0";
            src = fetchPypi {
              inherit pname version;
              sha256 = "7cf97ad1ddc860e250c3453e229897ed1273095ad061c34baf651bf1b0e5a9c7";
            };
            doCheck = false;
            propagatedBuildInputs = [
              pkgs.python3Packages.arrow
              pkgs.python3Packages.pytz
	            pkgs.python3Packages.requests
            ];
          }
        )
      ]))
    ];
}

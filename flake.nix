{
  description = "Staffeli NT - Canvas API tool for managing course assignments";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-compat = {
      url = "github:edolstra/flake-compat";
      flake = false;
    };
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, uv2nix, pyproject-nix, pyproject-build-systems, ... }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};

          # Load workspace from uv.lock
          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

          # Create overlay with pyproject-build-systems
          overlay = workspace.mkPyprojectOverlay {
            sourcePreference = "wheel";
          };

          # Create base Python set
          baseSet = pkgs.callPackage pyproject-nix.build.packages {
            python = pkgs.python314;
          };

          # Apply overlays to create final Python set
          pythonSet = baseSet.overrideScope (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.default
              overlay
            ]
          );

          # Create virtual environment with all dependencies
          venv = pythonSet.mkVirtualEnv "staffeli-nt-dev-env" workspace.deps.all;

        in
        {
          default = pkgs.mkShell {
            packages = [
              venv
              pkgs.uv
            ];

            shellHook = ''
              echo "Staffeli NT development environment"
              echo "Python: $(python --version)"
              echo ""
              echo "Available commands:"
              echo "  staffeli - Run staffeli CLI"
              echo "  uv run mypy -p staffeli_nt - Type checking"
              echo "  uv run ruff check staffeli_nt/ - Linting"
              echo "  uv run ruff format staffeli_nt/ - Formatting"
            '';
          };
        });
    };
}

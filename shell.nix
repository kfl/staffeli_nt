# This file provides backwards compatibility for users without flakes enabled.
# It uses flake-compat to wrap the flake.nix.
#
# Flake users should use: nix develop
# Non-flake users can use: nix-shell
(import (
  let
    lock = builtins.fromJSON (builtins.readFile ./flake.lock);
    flakeCompat = lock.nodes.flake-compat.locked;
  in
    fetchTarball {
      url = "https://github.com/${flakeCompat.owner}/${flakeCompat.repo}/archive/${flakeCompat.rev}.tar.gz";
      sha256 = flakeCompat.narHash;
    }
) {
  src = ./.;
}).shellNix

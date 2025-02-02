{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-compat.url = "https://flakehub.com/f/edolstra/flake-compat/1.tar.gz";
  };
  outputs =
    { nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" ];
      eachSystem = nixpkgs.lib.genAttrs systems;
    in
    rec {
      packages = eachSystem (
        system:
        let
          pkgs = import nixpkgs {
            inherit system;
            overlays = [ overlays.default ];
          };
        in
        {
          perforator = pkgs.perforator;
          default = pkgs.perforator;
        }
      );

      overlays.default = (
        final: prev: {
          perforator = final.callPackage ./nix { };
        }
      );
    };
}

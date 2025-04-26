{
  description = "I/O Communication Library";
  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    ahio.url = "github:acristoffers/ahio";
    ahio.inputs.nixpkgs.follows = "nixpkgs";
    ahio.inputs.flake-utils.follows = "flake-utils";
  };
  outputs = { self, nixpkgs, flake-utils, ahio }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      rec {
        moirai = pythonPkgs: pythonPkgs.buildPythonPackage {
          format = "pyproject";
          name = "moirai";
          src = ./.;
          propagatedBuildInputs = with pythonPkgs; [
            (ahio.ahio.${system} pythonPkgs)
            appdirs
            cheroot
            flask
            hatchling
            mysql-connector
            numpy
            pymongo
            python-dateutil
            scipy
          ];
        };
        packages.default = moirai pkgs.python311Packages;
        apps = rec {
          moirai = { type = "app"; program = "${packages.default}/bin/moirai"; };
          default = moirai;
        };
      });
}

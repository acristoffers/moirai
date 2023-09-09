{
  description = "I/O Communication Library";
  inputs = {
    flake-utils.url = github:numtide/flake-utils;
    nixpkgs.url = github:NixOS/nixpkgs/nixos-unstable;
    ahio.url = github:acristoffers/ahio;
  };
  outputs = { self, nixpkgs, flake-utils, ahio }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      rec {
        moirai = pythonPkgs: pythonPkgs.buildPythonPackage rec {
          format = "pyproject";
          name = "moirai";
          src = ./.;
          propagatedBuildInputs = with pythonPkgs; [
            (ahio.ahio.${system} pythonPkgs)
            appdirs
            cheroot
            flask
            mysql-connector
            numpy
            poetry-core
            pymongo
            python-dateutil
            scipy
          ];
        };
        packages.default = moirai pkgs.python311Packages;
      });
}

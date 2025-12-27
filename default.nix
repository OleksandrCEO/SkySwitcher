# default.nix

{ pkgs ? import <nixpkgs> {} }:

let
  pythonScript = pkgs.writers.writePython3Bin "skyswitcher" {
    libraries = [ pkgs.python3Packages.evdev ];
    flakeIgnore = [ "E501" ];
  } (builtins.readFile ./main.py);
in
pkgs.symlinkJoin {
  name = "skyswitcher";
  paths = [ pythonScript ];
  buildInputs = [ pkgs.makeWrapper ];
  postBuild = ''
    wrapProgram $out/bin/skyswitcher \
      --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.wl-clipboard ]}
  '';
}
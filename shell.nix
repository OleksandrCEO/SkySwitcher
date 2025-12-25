{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    (pkgs.python3.withPackages (ps: [ ps.evdev ]))
    pkgs.wl-clipboard
    pkgs.evtest
  ];
}

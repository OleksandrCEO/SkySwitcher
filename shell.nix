{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    (pkgs.python3.withPackages (ps: [ ps.evdev ]))
    pkgs.evtest
  ];

  shellHook = ''
    echo "SkySwitcher environment loaded."
    echo "Run: python3 main.py"
  '';
}
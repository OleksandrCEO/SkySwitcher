{ pkgs ? import <nixpkgs> {} }:

let
  # 1. Створюємо "сирий" скрипт (тільки Python + evdev)
  rawScript = pkgs.writers.writePython3Bin "skyswitcher" {
    libraries = [ pkgs.python3Packages.evdev ];
    flakeIgnore = [ "E501" ];
  } (builtins.readFile ./main.py);

in
  # 2. Робимо фінальний пакет, додаючи wl-clipboard у PATH скрипта
  pkgs.runCommand "skyswitcher" {
    buildInputs = [ pkgs.makeWrapper ];
  } ''
    mkdir -p $out/bin
    
    # Створюємо обгортку: запускаємо rawScript, але додаємо wl-clipboard у видимість
    makeWrapper ${rawScript}/bin/skyswitcher $out/bin/skyswitcher \
      --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.wl-clipboard ]}
  ''
# module.nix
{ config, lib, pkgs, ... }:

let
  cfg = config.services.skyswitcher;
in
{
  options.services.skyswitcher = {
    enable = lib.mkEnableOption "SkySwitcher package and permissions";
  };

  config = lib.mkIf cfg.enable {
    # [cite_start]1. Додаємо пакет у систему (щоб команда 'skyswitcher' була доступна всюди) [cite: 11]
    environment.systemPackages = [
      pkgs.skyswitcher
      pkgs.wl-clipboard
    ];

    # [cite_start]2. Налаштовуємо права доступу до uinput та створюємо групи [cite: 13]
    # Це дозволить скрипту працювати без sudo
    hardware.uinput.enable = true;
  };
}
# module.nix

{ config, lib, pkgs, ... }:

let
  cfg = config.services.skyswitcher;
in
{
  options.services.skyswitcher = {
    enable = lib.mkEnableOption "SkySwitcher service";
  };

  config = lib.mkIf cfg.enable {
    # 1. Автоматично додаємо пакет у систему
    environment.systemPackages = [
      pkgs.skyswitcher
      pkgs.wl-clipboard
    ];

    # 2. Додаємо оверлей, щоб pkgs.skyswitcher існував
    nixpkgs.overlays = [
      (final: prev: {
        skyswitcher = import ./default.nix { pkgs = prev; };
      })
    ];

    # 3. Налаштовуємо групи (тут ми чесно кажемо користувачу, що треба права)
    hardware.uinput.enable = true;

    # Автоматичне створення Systemd сервісу (за бажанням)
    systemd.user.services.skyswitcher = {
      description = "SkySwitcher Layout Fixer";
      wantedBy = [ "graphical-session.target" ];
      after = [ "graphical-session.target" ];
      serviceConfig = {
        ExecStart = "${pkgs.skyswitcher}/bin/skyswitcher";
        Restart = "always";
      };
    };
  };
}
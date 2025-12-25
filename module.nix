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
    # 1. Пакет
    # (Ми розраховуємо, що pkgs.skyswitcher доступний через overlay у flake.nix)
    environment.systemPackages = [
      pkgs.skyswitcher
      pkgs.wl-clipboard
    ];

    # 2. Права доступу
    # Це створює групу uinput та правила udev
    hardware.uinput.enable = true;

    # 3. Systemd сервіс
    systemd.user.services.skyswitcher = {
      description = "SkySwitcher Layout Fixer";

      # Запускаємось, коли користувач увійшов у систему (надійно)
      wantedBy = [ "default.target" ];

      # Прив'язуємось до графічної сесії (щоб сервіс зупинявся при виході)
      partOf = [ "graphical-session.target" ];

      # Намагаємось стартувати після графіки (Wayland/X11)
      after = [ "graphical-session.target" ];

      serviceConfig = {
        ExecStart = "${pkgs.skyswitcher}/bin/skyswitcher";
        Restart = "always";
        RestartSec = "3"; # Чекаємо 3 сек перед перезапуском, якщо впаде
      };
    };
  };
}
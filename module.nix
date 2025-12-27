{ config, lib, pkgs, ... }:

let
  cfg = config.services.skyswitcher;
in
{
  options.services.skyswitcher = {
    enable = lib.mkEnableOption "SkySwitcher package";
  };

  config = lib.mkIf cfg.enable {
    # 1. Install the package to system path so it can be found by KDE Autostart
    environment.systemPackages = [ pkgs.skyswitcher ];

    # 2. Create uinput group for managing /dev/uinput permissions
    users.groups.uinput = {};

    # 3. Enable uinput kernel module
    boot.kernelModules = [ "uinput" ];

    # 4. Set permissions for /dev/uinput device
    services.udev.extraRules = ''
      KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="uinput", MODE="0660"
    '';
  };
}
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
    environment.systemPackages = [
      pkgs.skyswitcher
    ];

    # Enable uinput device access for keyboard input emulation
    hardware.uinput.enable = true;
  };
}
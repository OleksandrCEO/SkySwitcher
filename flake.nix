# flake.nix

{
  description = "SkySwitcher - Keyboard layout switcher for Linux";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs }:
    let
      # Support multiple systems
      supportedSystems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgsFor = system: nixpkgs.legacyPackages.${system};
    in
    {
      # Package outputs for each system
      packages = forAllSystems (system: {
        default = import ./default.nix { pkgs = pkgsFor system; };
        skyswitcher = self.packages.${system}.default;
      });

      # Development shell for each system
      devShells = forAllSystems (system: {
        default = (pkgsFor system).mkShell {
          buildInputs = with (pkgsFor system); [
            (python3.withPackages (ps: [ ps.evdev ]))
            evtest
          ];
          shellHook = ''
            echo "SkySwitcher development environment"
            echo "Run: python3 main.py --verbose"
          '';
        };
      });

      # NixOS module (system-independent)
      nixosModules.default = import ./module.nix;
      nixosModules.skyswitcher = self.nixosModules.default;

    };
}
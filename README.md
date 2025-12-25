# SkySwitcher 🌌

![NixOS](https://img.shields.io/badge/NixOS-25.11+-5277C3?style=flat&logo=nixos&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

**SkySwitcher** is a minimalist, context-aware keyboard layout switcher for Linux (Wayland & X11). It fixes what you just typed without making you retype it.

Designed with **NixOS Flakes** in mind for reproducible and secure deployment.

## ✨ Features

- **⚡ Double Right Shift:** Tap `Right Shift` twice to switch layout (e.g., English ↔ Ukrainian).
- **📝 Auto-Correction:** It automatically corrects the **last typed word** when you switch.
  - *Typed `ghbdsn`? -> Double Shift -> Becomes `привіт`.*
- **🎯 Selection Fix:** Hold `Right Ctrl` + press `Right Shift` to fix the currently **selected text**.
- **🔒 Secure:** Runs with standard user permissions (via `uinput` group), no `sudo` required after setup.
- **❄️ Pure Nix:** Zero global dependencies. Builds cleanly from the Nix Store.

---

## 🚀 Quick Install (Imperative)

If you just want to try it out without modifying your system config:

    # Run directly from GitHub
    nix run github:OleksandrCEO/SkySwitcher -- --help

    # Or install to your profile
    nix profile install github:OleksandrCEO/SkySwitcher

---

## ❄️ NixOS Installation (Declarative)

The recommended way to install SkySwitcher is via **Flakes**. This ensures the script is built using your system's libraries (saving disk space) and is available globally as `skyswitcher`.

### 1. Add Input
Add the repository to your `/etc/nixos/flake.nix`:

    inputs = {
      nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";

      skyswitcher = {
        url = "github:OleksandrCEO/SkySwitcher";
        inputs.nixpkgs.follows = "nixpkgs"; # Uses your system's libs to save space
      };
    };

### 2. Configure Overlay & Package
Pass the input to your outputs and apply the overlay. This makes `skyswitcher` available in `pkgs`.

    # /etc/nixos/flake.nix
    {
      inputs = {
        # Use the same NixOS version as your system
        nixpkgs.url = "github:nixos/nixpkgs/nixos-25.11";
    
        # Add SkySwitcher input
        skyswitcher = {
          url = "github:OleksandrCEO/SkySwitcher";
          inputs.nixpkgs.follows = "nixpkgs"; # Optimization: use system packages
        };
      };
    
      outputs = { self, nixpkgs, skyswitcher, ... }: {
        nixosConfigurations.my-machine = nixpkgs.lib.nixosSystem {
          system = "x86_64-linux";
          modules = [
            ./configuration.nix
            
            # --- The Integration Part ---
            ({ config, pkgs, ... }: {
              # 1. Overlay: Makes 'skyswitcher' available in pkgs
              nixpkgs.overlays = [
                (final: prev: {
                  skyswitcher = skyswitcher.packages.${prev.system}.default;
                })
              ];
    
              # 2. Install
              environment.systemPackages = [ pkgs.skyswitcher ];
    
              # 3. Permissions (Required for uinput)
              hardware.uinput.enable = true;
              users.users.YOUR_USERNAME.extraGroups = [ "uinput" "input" ];
            })
          ];
        };
      };
    }

> **Note:** Don't forget to replace `YOUR_USERNAME` with your actual username.
> Run `sudo nixos-rebuild switch` and **reboot** to apply group permissions.

---

## 🤖 Auto-Start (Systemd)

To make SkySwitcher run automatically in the background:

### Option A: Home Manager (Recommended)

    systemd.user.services.skyswitcher = {
      Unit = {
        Description = "SkySwitcher Layout Corrector";
        After = [ "graphical-session.target" ];
      };
      Service = {
        ExecStart = "${pkgs.skyswitcher}/bin/skyswitcher";
        Restart = "always";
      };
      Install = {
        WantedBy = [ "graphical-session.target" ];
      };
    };

### Option B: Manual Systemd
Create `~/.config/systemd/user/skyswitcher.service`:

    [Unit]
    Description=SkySwitcher Layout Corrector
    After=graphical-session.target

    [Service]
    ExecStart=/run/current-system/sw/bin/skyswitcher
    Restart=always

    [Install]
    WantedBy=default.target

Then enable it: `systemctl --user enable --now skyswitcher`

---

## 🛠️ Usage & Troubleshooting

**Manual Run:**

    skyswitcher --verbose

**Arguments:**
- `-v, --verbose`: Show debug logs (key presses, conversions).
- `-d, --device`: Manually specify input device path.
- `--list`: List available input devices.

**Common Issues:**
- *Permission Denied:* Ensure your user is in the `input` and `uinput` groups.
- *Wayland Clipboard:* Ensure `wl-clipboard` is installed (it is included in dependencies, but check your environment).

---

## 📜 License

MIT License. Feel free to use and modify.
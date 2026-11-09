# Dev environment for NixOS, where pip's Pillow wheel can't find system libs.
# Used automatically by ./dev.sh.
{ pkgs ? import <nixpkgs> { } }:
pkgs.mkShell {
  packages = [ (pkgs.python3.withPackages (p: [ p.pillow p.markdown ])) ];
}

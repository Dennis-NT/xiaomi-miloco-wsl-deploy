# v0.1.0 - First public WSL deployment release

This is the first public release of a deployment-oriented Windows WSL distribution for Xiaomi Miloco + Micam + go2rtc.

## What this release focuses on

- A reproducible deployment path for `Windows + WSL Ubuntu 24.04`
- Native Docker Engine inside WSL instead of Docker Desktop managed runtime
- A working `Miloco + Micam + go2rtc` stack
- Practical deployment docs for setup, validation and redeploy
- Environment-specific fixes verified in a real WSL setup

## Included fixes

- WSL mirrored networking deployment guidance
- Hyper-V firewall rule guidance for camera connectivity
- Micam fix for `VIDEO_CODEC` environment variable handling
- Miloco build-time patches for this environment
- Frontend fix for the enlarged video modal showing only part of the frame

## Recommended runtime

- Windows 11
- WSL Ubuntu 24.04
- Native Docker Engine in WSL
- Chrome for validation and playback

## Notes

- This repository is a deployment-enhanced distribution assembled from upstream projects.
- Please review upstream licenses and usage terms before redistribution or commercial use.
- In particular, review the terms of `XiaoMi/xiaomi-miloco` carefully.

## Getting started

- Quick start: `docs/5分钟快速部署版.md`
- Full redeploy guide: `docs/再次部署指南.md`
- Public release checklist: `docs/公开发布前检查清单.md`

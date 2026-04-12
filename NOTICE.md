# Notice

This repository is a deployment-oriented, patched distribution assembled from multiple upstream projects.

Upstream projects:

- `miiot/micam`: https://github.com/miiot/micam
- `XiaoMi/xiaomi-miloco`: https://github.com/XiaoMi/xiaomi-miloco
- `AlexxIT/go2rtc`: https://github.com/AlexxIT/go2rtc

What this repository adds:

- a Windows + WSL Ubuntu 24.04 deployment path that was tested end-to-end
- native Docker Engine setup for WSL instead of Docker Desktop managed runtime
- Miloco build-time patches for this environment
- Micam runtime fixes and public-facing deployment documentation
- a frontend patch for the enlarged video modal canvas

License and usage notes:

- This repository does not replace, override, or relicense any upstream code.
- Please review and comply with the license and usage terms of every upstream project before redistributing or using this repository.
- In particular, check the `XiaoMi/xiaomi-miloco` repository terms carefully before any public or commercial use.

Sensitive local runtime files:

- `.env`
- `miloco/miloco.db`
- `miloco/cert/*`
- `miloco/log/*`
- `miloco/miot_cache/*`

These files are intentionally ignored by `.gitignore` and should not be committed to a public repository.

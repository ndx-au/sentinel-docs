# skill twin: sn.git-sync/kit.yaml

Manifest for the `sn.git-sync` kit. Keeps `public: false` and contains a single scheduled flow (`fl/sync.lua`) that runs `POST /git/sync` (or `/git/pull`) every 5 minutes only when explicitly enabled in the machine-local Sentinel vault.

# Main-looper retained replay + UI review

Reviewed saved evidence from `provider-app-collector-probe-20260913t121931z` only; no device or model action by Jens.

## Retained real-audio collector regression

Receipt: `private-extracted-01/files/player-ui-captures/provider-app-collector-probe-20260913t121931z/live-collector/.private-ui/replay.json` under `podcast-app/.local/progressive-ready/phone/provider-app-collector-probe-20260913t121931z/`.

Receipt SHA-256: `2894ee9814db552e243447fd2b793115f68fdcb05d9278bdc64cf13da293b21a`.

Verified:

- Exact app/test pair: `fe6ba7493bb1f3e3611a3994d0951f2a87006c983d9032349ebc6a3303ff5157` / `359dbe7ac8392f1cb7a4a607a9be0d37ed4b4699d30736cffd3ee235c3a255d8`.
- The real production repository IO collector delivered staged retained prefixes 1 → 2 → 5 → 15 to one Main-looper ExoPlayer (identity 75975702).
- Every paused prefix retained absolute position 500 ms, 1.25× speed, muted transport, and no playback intent/autoplay; media-item counts match available chunks.
- Explicit play advanced to 935 ms, then 1308 ms through isolated-fixture COMPLETE on the same player, with playback intent retained.
- Source master is `2194bce66f8abd05bdf10fefc5cf4aaef49cac647992f637db319b7d14be532a`; 36 copied source files and real episode/job/playback state were checked unchanged.
- Receipt explicitly says `realRepoIO=true`, `replay=true`, `htpConcurrency=false`, zero new model calls and zero real AUDIO jobs. The previously failing background-collector path now passes without wrong-thread access.

## UI verdict

Reviewed all eight PNGs from final `private-extracted-02`, verified each image SHA/byte count and sidecar identity. Default and 320dp/font2 mini-player insets and controls remain correct. Manual transcript availability transitions retain axes **3840** and **2200** respectively through 1/4/8/16 chunks, with unchanged viewport bounds. Explicit follow reveals the current segment. Full/mini captures retain the same per-profile session/player and speed. No visual regression or further source change requested.

## Boundary

**Pass for the targeted thread-affinity repair, retained-audio replay, and existing UI regressions.** This replay uses real retained PCM but staged in-memory availability, so it is not genuine concurrent HTP synthesis/playback and does not establish that missing gate. Janek is carrying the distinct authorized genuine run and exact tested deployment. The first failed genuine attempt and its Ready audio remain separate preserved outcomes.

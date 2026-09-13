# Genuine workflow request stopped at owned admission

**Not E2E PASS. Zero TTS constructions, loads or graph calls; no audio chunks, Player opening or Play.**

Distinct run `provider-app-genuine-20260913t101720z` used candidate09 `c18556a0bde17db7363db5c6ac7387572512cc69e842008bbc2ad188663b804e`, with exactly the same `7989af04…b82d` / `27e8d84c…a279` APK pair as the strengthened guard+8UI proof. Controller-only `f1dd201b` reused that exact proof rather than unnecessarily rerunning unchanged UI profiles immediately before neural admission.

Fresh host pre-inference headroom **3,228,548KiB**,32.6°C passed the provisional3GiB boundary. The normal UI created a labelled owned draft copy and requested one AUDIO job. After managed setup, the first in-process guard sample was **3,045,628KiB (~2.905GiB)**,32.7°C: about97.8MiB below the same3GiB starting boundary. No cause is attributed to that device-wide difference.

The guard emitted `ADMISSION`, durably changed only this owned attempt to FAILED, and requested self-termination of its generation process. `guard.start()` precedes `ttsFactory()` in the frozen coordinator, so no TTS engine construction/load/inference occurred. The subsequent90s Listen timeout is a consequence of the earlier admission failure, not evidence of a synthesis or Player defect. The driver retained the terminal owned failure and did not retry.

Owned episode `d610c2d3-3c0e-41a8-ae75-17d66cb47094`; attempt `80788714f6d01bf231579a88e4dfcf4d51e7474c4c735ea3a91c3314557102c5`. Its plan, revision and binding remain intact. The original11 episodes,17 jobs,63 episode files and other user rows were unchanged; only one new owned episode/source/revision/chapter/job and four owned files were added. No chapter-audio or playback row was added. Prior failed/recovered2194 evidence remains unchanged.

Cleanup errors0; provider control/staging root/processes absent; settings preserved; exact installed hashes reverified; phone.lock released. No background cleanup, floor change or automatic second AUDIO request followed this stop.

**Remaining boundary:** full progressive AUDIO/actual pre-Ready playback/mini/transcript/Ready E2E is still incomplete. Both host and in-process3GiB admission checks remain enforced; this result does not authorize silently changing their meaning or another attempt. The strengthened guard and UI passes remain valid within their stated non-neural scope.

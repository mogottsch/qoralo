# Reviewed guard and pending-transcript revalidation

**PASS for the strengthened non-neural guard plus8 synthetic UI cases. Not genuine AUDIO E2E.**

Source `a9b1bfef` batches the confirmed guard-teardown safety fix, fresh playback checks before every destructive package close, and Jens's stable planned provider transcript rows (`18e30f78`). Candidate `83b84789279939f2bd6c9a29f8e0683764cfd6ea2b58c6e20402154306eeb9a9` produced app `7989af04ab9e63dab4c97e4d515382c11852f2b97a8089e8bd673a581a7db82d` and test `27e8d84c1640f6494fb25d59cc22b79849e83ccb8f62218736faacd64b6da279`.

The earlier38ms sleeping-worker result did not cover managed cancellation followed by synchronous native-style destruction. This replacement probe specifically injects LOW_MEMORY, unwinds a managed guard check and blocks in the shared teardown path. The guard/lease stays active until destruction returns. It commits only the owned private failure and terminates only its process. Stop decision to observed PID absence: **53.884792ms**, with durable failure preceding termination. This is still a non-neural worker/private SQLite result, not a measured QNN destruction bound or an in-flight QNN cancellation API.

Both default and narrow/font2 profiles passed4/4 cases, including chunk arrivals0→1→4→8→16/COMPLETE while transcript following is disabled. Planned row keys/text and layout remain stable; verified timing attaches without replacing the pending row.9 Android cases passed total.236 JVM cases passed with1 pre-existing optional skip;12 Python checks passed at this freeze.

All original11 episodes/17 jobs/63 files and other user rows were preserved, settings restored, cleanup errors0. Installed hashes were reverified and phone.lock released. Native/model bytes unchanged. This exact APK/guard/8UI receipt is the prerequisite for the separately recorded provisional3GiB genuine evaluation, not its result.

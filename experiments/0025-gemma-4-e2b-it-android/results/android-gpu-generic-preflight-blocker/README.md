# Approved generic GPU route — transport preflight blocker

Moritz approved the official generic `gemma-4-E2B-it.litertlm` artifact with `Backend::GPU` as the amended canonical GPU route. The first provider-bound smoke attempt stopped before device identity capture because the authorized serial was absent from the configured Windows ADB bridge.

No stage was created, no process was launched, and no remote mutation occurred. This is transport evidence only, not a GPU route result. `phone.lock` was released immediately and independently verified free. Restore the authorized serial through `tcp:172.27.80.1:5037` before retrying the entirely fresh smoke.

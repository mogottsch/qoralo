#!/usr/bin/env python3
"""Pi's actual slot: read-only installed identity/quiescence under full lock."""
import hashlib
from pathlib import Path
import phone_selected_id_long as base

BASE_SHA='a417c3edbb2a1eda1f963951afc2070dc3fc0bca025173e34c8b3d5f0dea9b04'
EXPECTED={
 'dev.vibevoice.podcast.internal':'e1b33f276aa7f267c778a1c3fe6c113700aa401d61472956a4769a098fcc89ba',
 'dev.vibevoice.podcast.internal.test':'060edd5f0679b79ec928319a5b1e93c1bbcbd42d775b2df05c78307ad849d0f9'}
IDENTITY=r'''
for package in dev.vibevoice.podcast.internal dev.vibevoice.podcast.internal.test; do
  location=$(pm path "$package") || exit 41
  case "$location" in package:/data/app/*/base.apk) ;; *) exit 42 ;; esac
  case "$location" in *'
'*) exit 43 ;; esac
  path=${location#package:}
  value=$(sha256sum "$path") || exit 44
  hash=${value%% *}
  printf 'APK\t%s\t%s\n' "$package" "$hash"
done
'''
QUIESCENCE=r'''
command -v pidof >/dev/null || exit 45
for process in dev.vibevoice.podcast.internal dev.vibevoice.podcast.internal:generation dev.vibevoice.podcast.internal.test; do
  value=$(pidof "$process" 2>/dev/null)
  code=$?
  [ "$code" = 0 ] || [ "$code" = 1 ] || exit 46
  printf 'PID\t%s\t%s\n' "$process" "$value"
done
'''


def validate(data, identity=False):
    rows=[x.split('\t') for x in data.decode(errors='replace').splitlines()]
    apks={x[1]:x[2] for x in rows if len(x)==3 and x[0]=='APK'}
    pids={x[1]:x[2] for x in rows if len(x)==3 and x[0]=='PID'}
    if identity and apks!=EXPECTED:raise ValueError('installed app/test identity changed or unavailable; no restore/install')
    names=set(EXPECTED)|{'dev.vibevoice.podcast.internal:generation'}
    if set(pids)!=names:raise ValueError('target-app quiescence unavailable')
    if any(pids.values()):raise ValueError('target app process present: quiescence not established; no force-stop or model launch')
    return {'installed_sha256':apks if identity else None,'target_processes_absent':True,
            'boundary':'Conservative target-process absence, not a claim about all phone activity; no app/DB or process modifications.'}


def load_lifecycle():
    if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise RuntimeError('trace lifecycle changed')
    module,receipt=base.load_lifecycle();parent=module.Controller
    class AppGuardController(parent):
        def _identity(self):
            super()._identity()
            reply=self._shell('preflight.current_app_identity_quiescence',IDENTITY+QUIESCENCE,45)
            self.result['current_app_preflight']=validate(reply.stdout,True)
            self.result['current_app_guard_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        def _launch_and_wait(self):
            reply=self._shell('preflight.app_quiescence_before_launch',QUIESCENCE,10)
            self.result['app_quiescence_before_launch']=validate(reply.stdout)
            return super()._launch_and_wait()
    module.Controller=AppGuardController
    return module,receipt


if __name__=='__main__':
    lifecycle,_=load_lifecycle()
    raise SystemExit(lifecycle.main())

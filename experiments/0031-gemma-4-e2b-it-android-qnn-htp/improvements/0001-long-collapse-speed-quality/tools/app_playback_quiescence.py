#!/usr/bin/env python3
"""Streaming, UID-scoped playback observation. No audio dump in argv or files."""
import re
import shlex

AUDIO_FILTER=r'''
BEGIN { monitor=0; section=0; in_players=0; parse_error=0; upstream=-1; markers=0; own_active=0; own_inactive=0 }
/^GEMMA_AUDIO_SOURCE_EXIT [0-9]+$/ { upstream=$2+0; markers++; in_players=0; next }
{
 line=tolower($0)
 if (line ~ /playbackactivitymonitor/) { monitor=1; next }
 if (monitor && line ~ /^[[:space:]]*players:[[:space:]]*$/) {
   if (section) parse_error=1
   section=1; in_players=1; next
 }
 if (!in_players) next
 if (line ~ /^[[:space:]]*$/) { in_players=0; next }
 if (line ~ /^[[:space:]]*none[[:space:]]*$/) next
 # A new section header ends the current-player list. Never inspect event history.
 if (line ~ /^[[:space:]]*[^:]+:[[:space:]]*$/) { in_players=0; next }
 if (!match(line, /(u|uid)\/pid:[[:space:]]*[0-9]+\/[0-9]+/)) { parse_error=1; next }
 identity=substr(line,RSTART,RLENGTH);sub(/^.*pid:[[:space:]]*/,"",identity);split(identity,parts,"/"); owner=parts[1]
 if (!match(line, /state:[[:space:]]*[a-z_-]+/)) { parse_error=1; next }
 state=substr(line,RSTART,RLENGTH);sub(/^state:[[:space:]]*/,"",state)
 if (state!="started" && state!="starting" && state!="paused" && state!="stopped" && state!="released" && state!="idle") { parse_error=1; next }
 if (owner==target_uid) {
   if (state=="started" || state=="starting") own_active++
   else own_inactive++
 }
}
END {
 parse="ok";verdict="quiescent";code=0
 if (markers!=1) { parse="source_status_missing_or_duplicate";verdict="unknown";code=54 }
 else if (upstream!=0) { parse="upstream_error";verdict="unknown";code=54 }
 else if (!monitor || !section) { parse="missing_monitor_or_section";verdict="unknown";code=54 }
 else if (parse_error) { parse="malformed_player";verdict="unknown";code=54 }
 else if (own_active) { verdict="active";code=55 }
 printf "PLAYBACK_GUARD_V2 upstream=%d parse=%s own_active=%d own_inactive=%d verdict=%s\n",upstream,parse,own_active,own_inactive,verdict
 exit code
}
'''
UID_FILTER=r'''
/^GEMMA_UID_SOURCE_EXIT [0-9]+$/ { status=$2+0; markers++; next }
$1=="package:dev.vibevoice.podcast.internal" { value=$2;sub(/^uid:/,"",value);count++ }
END { if(markers==1 && status==0 && count==1 && value ~ /^[0-9]+$/) print value; else print "UNKNOWN" }
'''


def probe_script():
    return r'''main=$(pidof dev.vibevoice.podcast.internal 2>/dev/null); status=$?
[ "$status" = 0 ] || [ "$status" = 1 ] || { printf 'PLAYBACK_GUARD_V2 main=unknown verdict=unknown\n'; exit 51; }
if [ -z "$main" ]; then printf 'PLAYBACK_GUARD_V2 main=absent verdict=quiescent\n'; exit 0; fi
uid=$({ cmd package list packages -U dev.vibevoice.podcast.internal 2>/dev/null; status=$?; printf '\nGEMMA_UID_SOURCE_EXIT %s\n' "$status"; } | awk '''+shlex.quote(UID_FILTER)+r''')
case "$uid" in ''|*[!0-9]*) printf 'PLAYBACK_GUARD_V2 uid=unknown verdict=unknown\n'; exit 52;; esac
# Stream the source directly. Only its small exit-status marker is a printf argument.
{ dumpsys audio 2>/dev/null; status=$?; printf '\nGEMMA_AUDIO_SOURCE_EXIT %s\n' "$status"; } | awk -v target_uid="$uid" '''+shlex.quote(AUDIO_FILTER)+'\n'


def validate(data):
    text=data.decode(errors='replace').strip()
    if text=='PLAYBACK_GUARD_V2 main=absent verdict=quiescent':
        return {'main_absent':True,'playback_quiescence_observed':True,'audio_dump_requested':False,'generation_test_quiescence_checked_separately':True}
    match=re.fullmatch(r'PLAYBACK_GUARD_V2 upstream=(-?\d+) parse=([a-z_]+) own_active=(\d+) own_inactive=(\d+) verdict=([a-z]+)',text)
    if not match:raise ValueError('playback observation unavailable/malformed')
    code,parsed,active,inactive,verdict=match.groups()
    if code!='0' or parsed!='ok' or active!='0' or verdict!='quiescent':raise ValueError('playback not established: '+text)
    return {'main_absent':False,'upstream_exit':0,'parse_status':parsed,'owned_active_players':0,'owned_inactive_players':int(inactive),'playback_quiescence_observed':True,'boundary':'Current UID-scoped AudioPlaybackConfiguration observation plus separate generation/test checks and Pi job-quiescence attestation; no unrelated audio records retained.'}

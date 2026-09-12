from pathlib import Path
import sys,json,hashlib
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(TRACK/'tools'))
import phone_paired_prefill_capture as base
EXPECTED={'dev.vibevoice.podcast.internal': '04d9293b9a128730bac7a4a12a469b74ba367a4936b251cfa6ca4e253c3aef7f', 'dev.vibevoice.podcast.internal.test': '2dd4e0d89a38ec763dfd50ef101496c4f56e4f7db2cfaf1fa935fed6616d3184'}
JOB_PROBE='main=$(pidof dev.vibevoice.podcast.internal 2>/dev/null); code=$?\n[ "$code" = 0 ] || [ "$code" = 1 ] || exit 51\nif [ -z "$main" ]; then printf \'APP_MAIN_ABSENT\\n\'; exit 0; fi\nuid=$(cmd package list packages -U dev.vibevoice.podcast.internal | awk \'$1 == "package:dev.vibevoice.podcast.internal" { sub("uid:","",$2); print $2 }\')\ncase "$uid" in \'\'|*[!0-9]*) printf \'APP_AUDIO_UNKNOWN_UID\\n\'; exit 52;; esac\naudio=$(dumpsys audio) || exit 53\nprintf \'%s\\n\' "$audio" | awk -v uid="$uid" \'\nBEGIN { monitor=0; schema=0; own=0; active=0; unknown=0 }\n{ line=tolower($0)\n if (line ~ /playbackactivitymonitor/) monitor=1\n if (line ~ /u\\/pid:|uid\\/pid:/) schema=1\n if (line ~ ("u/id:" uid "/")) unknown++\n if (line ~ ("u/pid:[[:space:]]*" uid "/") || line ~ ("uid/pid:[[:space:]]*" uid "/")) {\n   own++\n   if (line ~ /state:[[:space:]]*(started|starting)/) active++\n   else if (line !~ /state:[[:space:]]*(paused|stopped|released|idle)/) unknown++\n }\n}\nEND { printf "APP_AUDIO_MONITOR %d SCHEMA %d OWN %d ACTIVE %d UNKNOWN %d\\n",monitor,schema,own,active,unknown;\n if (!monitor || !schema || active || unknown) exit 54 }\n\'\n'
module,receipt=base.load_lifecycle(EXPECTED,True)
parent=module.Controller
class ActualJobController(parent):
 def check_job(self,label):
  reply=self._shell(label,JOB_PROBE,30)
  text=reply.stdout.decode().strip()
  if text!='APP_MAIN_ABSENT' and not (text.startswith('APP_AUDIO_MONITOR 1 SCHEMA 1 ') and 'ACTIVE 0 UNKNOWN 0' in text):raise module.GuardError('actual job/playback quiescence not established; no user-work stop')
  self.result[label]={'read_only_observation':text,'generation_and_test_absence_checked_by_base':True,'Pi_actual_job_quiescence_attestation':True,'idle_main_not_called_generation':True,'unrelated_audio_dump_not_retained':True}
 def _identity(self):
  super()._identity();self.check_job('preflight.actual_user_job_playback')
 def _launch_and_wait(self):
  self.check_job('prelaunch.actual_user_job_playback');return super()._launch_and_wait()
module.Controller=ActualJobController
(ROOT/'scope-binding.json').write_text(json.dumps({'readiness':receipt,'job_probe_sha256':hashlib.sha256(JOB_PROBE.encode()).hexdigest(),'probe_scope':'only target process/UID playback booleans; no unrelated audio records retained'},indent=2)+'\n')
sys.argv=[sys.argv[0],'--execute','--reviewed-stage-digest',base.STAGE_DIGEST,'--pi-slot','pi-gemma-paired-20260912T135612Z-01','--run-id','paired-prefill-20260912T135612Z-01']
code=module.main();(ROOT/'controller-exit.json').write_text(json.dumps({'actual_controller_exit':code})+'\n');raise SystemExit(code)

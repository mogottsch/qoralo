from pathlib import Path
import sys,json
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(TRACK/'tools'))
from phone_legacy_prefill_capture import load_adapter
controller,binding=load_adapter();(ROOT/'adapter-binding.json').write_text(json.dumps(binding,indent=2)+'\n')
sys.argv=[sys.argv[0],'--execute','--reviewed-stage-digest',controller.STAGE_DIGEST,'--pi-slot','pi-gemma-legacy-prefill-20260913T125558Z-01','--run-id','legacy-prefill-20260913T125558Z-01','--expected-app-sha256','119e0f92640f258374065c134c14af22ba0131e3e866df17842e7d974f613c34','--expected-test-sha256','7ae210bf1e03db73f53cd298fcd17b7fe7da5cb06a69f0afdeb775e12f27d4d8','--pi-user-job-quiescent']
result=controller.main();(ROOT/'controller-exit.json').write_text(json.dumps({'actual_controller_exit':result})+'\n');raise SystemExit(result)

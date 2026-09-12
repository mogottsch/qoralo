from pathlib import Path
import sys,json
TRACK=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(TRACK/'tools'))
import phone_paired_prefill_capture as controller
sys.argv=[sys.argv[0],'--execute','--reviewed-stage-digest',controller.STAGE_DIGEST,'--pi-slot','pi-gemma-paired-20260912T140747Z-02','--run-id','paired-prefill-20260912T140747Z-02','--expected-app-sha256','04d9293b9a128730bac7a4a12a469b74ba367a4936b251cfa6ca4e253c3aef7f','--expected-test-sha256','2dd4e0d89a38ec763dfd50ef101496c4f56e4f7db2cfaf1fa935fed6616d3184','--pi-user-job-quiescent']
code=controller.main();(ROOT/'controller-exit.json').write_text(json.dumps({'actual_controller_exit':code})+'\n');raise SystemExit(code)

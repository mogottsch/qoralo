TOOLS='/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/tools'
import sys,hashlib
from pathlib import Path
sys.path.insert(0,TOOLS)
import phone_aligned_litert_reference as p
from phone_selected_id_appguard import IDENTITY,EXPECTED
module,_=p.load_lifecycle()
Parent=module.Controller
class PostIdentityController(Parent):
    def _finish_remote(self):
        super()._finish_remote()
        if not self.result.get("identity_verified"):return
        try:
            reply=self._shell("postflight.current_app_identity",IDENTITY,45)
            rows=[x.split("\t") for x in reply.stdout.decode().splitlines()]
            if len(rows)!=2 or any(len(x)!=3 or x[0]!="APK" for x in rows):raise ValueError("postflight APK identity unavailable")
            actual={x[1]:x[2] for x in rows}
            self.result["postflight_installed_app_identity"]={"observed":actual,"unchanged":actual==EXPECTED}
            if actual!=EXPECTED:raise ValueError("postflight installed app/test hash mismatch; no restore attempted")
        except Exception as error:
            self.result["postflight_identity_error"]=str(error)
            self.result.setdefault("error",{"phase":"postflight_identity","message":str(error)})
        self.result["postflight_wrapper_sha256"]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
module.Controller=PostIdentityController
raise SystemExit(module.main())

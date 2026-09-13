from pathlib import Path
import subprocess,json,hashlib,time,os
track=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');out=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/paired-legacy-logits/build-01');os.umask(0o077)
subprocess.run(['/usr/bin/python3','-B',str(track/'tools/prepare_legacy_prefill_logits.py'),'--output-dir',str(out)],check=True,close_fds=True)
src=out/'sdk-source/examples/Genie/Genie';cmd=['/home/moritz/Android/Sdk/ndk/28.1.13356709/ndk-build','-C',str(src),'APP_ALLOW_MISSING_DEPS=true','APP_ABI=arm64-v8a','NDK_PROJECT_PATH=./','NDK_APPLICATION_MK=make/Application.mk','APP_BUILD_SCRIPT=make/Android.mk','-j2'];(out/'build-command.json').write_text(json.dumps(cmd,indent=2)+'\n');start=time.monotonic()
with (out/'native.stdout').open('xb') as so,(out/'native.stderr').open('xb') as se:p=subprocess.run(cmd,stdout=so,stderr=se,timeout=1700,close_fds=True)
binary=src/'libs/arm64-v8a/libGenie.so';result={'actual_native_exit':p.returncode,'seconds':time.monotonic()-start,'binary':str(binary),'model_or_phone_executed':False}
if p.returncode==0:result.update(binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),binary_bytes=binary.stat().st_size)
(out/'build-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(p.returncode)

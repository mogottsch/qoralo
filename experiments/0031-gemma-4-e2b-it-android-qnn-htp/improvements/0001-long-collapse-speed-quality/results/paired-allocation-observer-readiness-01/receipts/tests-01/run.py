from pathlib import Path
import subprocess,json
root=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/paired-allocation-observer/tests-01');track=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality')
cmd=['g++','-std=c++20','-O0','-pthread','-I'+str(track/'tools'),str(root/'test.cpp'),'-Wl,--wrap=malloc','-Wl,--wrap=calloc','-Wl,--wrap=realloc','-o',str(root/'test')]
p=subprocess.run(cmd,capture_output=True,timeout=40);(root/'compile.stdout').write_bytes(p.stdout);(root/'compile.stderr').write_bytes(p.stderr);assert p.returncode==0,p.stderr.decode()
p=subprocess.run([str(root/'test'),str(root/'capture')],capture_output=True,timeout=10);(root/'test.stdout').write_bytes(p.stdout);(root/'test.stderr').write_bytes(p.stderr);assert p.returncode==0,p.returncode
lines=(root/'capture/allocation-stages.log').read_text().splitlines();records=[dict(piece.split('=',1) for piece in line.split()[1:]) for line in lines]
assert len(records)<=64
first=records[0];assert first['vector_requested_bytes']=='24' and first['vector_size']=='5' and first['vector_capacity']=='6' and int(first['memory_valid_bits'])&7==7
failure=next(r for r in records if r['stage']=='test.failure' and r['phase']=='throw');assert failure['requested_elements_valid']=='0' and failure['errno_at_observation']=='28'
result={'compile_exit':0,'synthetic_exit':0,'logger_Cplusplus_new_and_link_wrapped_malloc_calloc_realloc_forbidden_test_passed':True,'original_calls_and_return_values_preserved':True,'original_exception_preserved':True,'errno_snapshot_preserved_and_labelled_observation':True,'overflow_diagnostic_checked':True,'self_memory_and_rlimit_readbacks_observed':True,'CLOEXEC_verified':True,'record_count':len(records),'bytes':(root/'capture/allocation-stages.log').stat().st_size,'full_model_or_phone_executed':False}
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

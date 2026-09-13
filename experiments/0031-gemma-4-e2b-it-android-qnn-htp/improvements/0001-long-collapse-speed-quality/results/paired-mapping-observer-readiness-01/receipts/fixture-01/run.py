from pathlib import Path
import json,subprocess,sys,shutil
root=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/paired-mapping-observer/fixture-01');track=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');sys.path.insert(0,str(track/'tools'));import prepare_mapping_stage_capture as prep
src=prep.BASE/(prep.CPP+'MmappedFile/src/MmappedFile.cpp');(root/'original.cpp').write_bytes(src.read_bytes());(root/'observed.cpp').write_text(prep.patch_mmap(src.read_text()));headers=root/'headers/qualla';headers.mkdir(parents=True)
for name in ['allocation_stage_trace.hpp','mapping_stage_trace.hpp']:shutil.copyfile(track/'tools'/name,headers/name)
(root/'embedding_int8_lut.bin').write_bytes(bytes(4096));results=[]
for mode in ['original','observed']:
 cmd=['g++','-std=c++20','-O0','-pthread','-I'+str(prep.BASE/(prep.CPP+'MmappedFile/include')),'-I'+str(root/'headers'),str(root/(mode+'.cpp')),str(root/'test.cpp'),'-Wl,--wrap=mmap','-Wl,--wrap=malloc','-Wl,--wrap=calloc','-Wl,--wrap=realloc','-o',str(root/mode)]
 if mode=='observed':cmd.insert(1,'-DWITH_OBSERVER')
 (root/(mode+'-command.json')).write_text(json.dumps(cmd,indent=2)+'\n');p=subprocess.run(cmd,capture_output=True,timeout=30);(root/(mode+'-compile.stdout')).write_bytes(p.stdout);(root/(mode+'-compile.stderr')).write_bytes(p.stderr);assert p.returncode==0,p.stderr.decode()
 for failure in [0,1]:
  run=root/(mode+'-'+str(failure));run.mkdir();p=subprocess.run([str(root/mode),str(root/'embedding_int8_lut.bin'),str(run),str(failure)],capture_output=True,timeout=10);(run/'stdout.txt').write_bytes(p.stdout);(run/'stderr.txt').write_bytes(p.stderr);assert p.returncode==0,(mode,failure,p.returncode)
  row={'mode':mode,'injected_failure':bool(failure),'exit':p.returncode,'summary':p.stdout.decode().strip()}
  if mode=='observed':
   text=(run/'mapping-stages.log').read_text();records=[dict(item.split('=',1) for item in line.split()[1:]) for line in text.splitlines()];assert len(records)<=32 and len(text)<=32768
   mapped=[x for x in records if x['phase']=='mmap.after'];opened=[x for x in records if x['phase']=='file.open.return'];assert len(mapped)==len(opened)==2
   assert all(x['requested_file_bytes']=='4096' for x in mapped)
   if failure:assert all(x['address_is_MAP_FAILED']=='1' and x['errno_at_observation']=='12' for x in mapped) and all(x['File_open_return']=='1' and x['isOpen']=='0' and x['mapped_bytes']=='0' for x in opened)
   else:assert all(x['address_is_MAP_FAILED']=='0' and x['mapped_bytes']=='4096' for x in mapped) and all(x['File_open_return']=='1' and x['isOpen']=='1' for x in opened)
   row.update(log_events=len(records),log_bytes=len(text),CLOEXEC_and_no_authored_heap_calls_passed=True)
  results.append(row)
assert results[0]['summary']==results[2]['summary'] and results[1]['summary']==results[3]['summary']
result={'classification':'tiny_injected_mmap_failure_contract_fixture','cases':results,'original_and_observed_results_equal':True,'forced_MAP_FAILED_ENOMEM_can_leave_open_return_true_pointer_null_size0':True,'fixture_proves_actual_Android_cause':False,'AS_changed':False,'phone_or_model_executed':False};(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

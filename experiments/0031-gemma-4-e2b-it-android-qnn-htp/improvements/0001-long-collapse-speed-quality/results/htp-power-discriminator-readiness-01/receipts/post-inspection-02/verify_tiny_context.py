from pathlib import Path
import sys,json
track=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality');out=Path('/home/moritz/dev/vibevoice-android-spike/experiments/0031-gemma-4-e2b-it-android-qnn-htp/improvements/0001-long-collapse-speed-quality/.local/htp-power-discriminator/post-inspection-02');sys.path.insert(0,str(track/'tools'));from prepare_htp_power_discriminator import inspect,verify_context_contract,expected_cases
prep=track/'.local/htp-power-discriminator/prepare-02';graphs=[];formulas=[]
for name in ['power_edge','normalization_chain','normalization_exposed']:
 desc=json.loads((prep/name/'authored.json').read_text());g=inspect(prep/name/(name+'.dlc'),desc);graphs.append(g);formulas.append(expected_cases(desc))
result=verify_context_contract(json.loads((prep/'context-info.json').read_text()),graphs);(out/'graphs.json').write_text(json.dumps(graphs,indent=2)+'\n');(out/'expected-formulas.json').write_text(json.dumps(formulas,indent=2)+'\n');(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

#!/usr/bin/env python3
import argparse,hashlib,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--logs',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('names',nargs='+');a=p.parse_args()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out={'schema_version':1,'gates':{}}
for name in a.names:
 d=a.logs/name;err=(d/'stderr.log').read_text(errors='replace');stdout=(d/'stdout.log').read_text(errors='replace');caps=[{'partitions':int(x),'graph_nodes':int(y),'qnn_nodes':int(z)} for x,y,z in re.findall(r'Number of partitions supported by QNN EP: (\d+), number of nodes in the graph: (\d+), number of nodes supported by QNN: (\d+)',err)]
 lines=[x for x in err.splitlines() if 'Unsupported nodes in QNN EP:' in x]
 unsupported=[]
 if lines:
  clean=re.sub(r'\x1b\[[0-9;]*m','',lines[-1]);unsupported=[{'name':n,'op_type':t} for n,t in re.findall(r'\{ name: (.*?), type: (.*?) \}',clean)]
 out['gates'][name]={'exit_code':int((d/'exit-code.txt').read_text()),'capability_passes':caps,'unsupported_nodes':unsupported,'unsupported_count':len(unsupported),'stdout_sha256':sha(d/'stdout.log'),'stderr_sha256':sha(d/'stderr.log')}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')

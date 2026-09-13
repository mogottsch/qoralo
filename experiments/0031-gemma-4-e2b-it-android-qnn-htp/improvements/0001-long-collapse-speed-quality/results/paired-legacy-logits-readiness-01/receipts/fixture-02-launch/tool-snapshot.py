#!/usr/bin/env python3
"""Synthetic backend only: compile real PLE dispatch and final dequant/capture path."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from prepare_legacy_prefill_logits import TRACK,BASE,REL,EXPECTED,patch,sha
Q=BASE/'examples/Genie/Genie/src/qualla'
ENGINE_SHA='e060a8ddc4195fa1ddc6adeeba4a2bae4b5a86d305db5c3affdd6853d86c2e22'
BASE_HEADER_SHA='58e61c1ab8d9b16896296df929d36e3cbfe2aa14709a436fae4382f5c6b7b466'

STUB=r'''
#include "qualla/prefill_capture.hpp"
#include <algorithm>
#include <cassert>
#include <fstream>
#include <map>
#include <span>
#include <vector>
#include <cstdint>
#define GENIE_TRACE(...) ((void)0)
#define __TRACE(...) ((void)0)
#define __DEBUG(...) ((void)0)
#define PRAGMA_LOOP_VECTORIZE
constexpr size_t VOCAB=262144, ROWS=128;
constexpr double SCALE=0.0008891067700460553;
constexpr int32_t OFFSET=-31869;
static std::vector<uint16_t> raw_rows;
static bool expect_capture=false;
static unsigned dequant_calls=0, synthetic_backend_calls=0, sampler_calls=0;
static bool capture_seen_before_dequant=false;
namespace qualla {struct Timer {size_t elapsed_usec(){return 0;}};}
namespace State {inline void error(const std::string&){std::abort();}}
namespace fmt {template<class... T> std::string format(const char*,T...){return "fixture error";}}
enum {QNN_DATATYPE_UFIXED_POINT_8,QNN_DATATYPE_UFIXED_POINT_16,QNN_DATATYPE_FLOAT_16,QNN_DATATYPE_FLOAT_32,TENSOR_DATATYPE_FLOAT_32};
namespace QnnUtils {
struct DataType {int value;DataType(int v=QNN_DATATYPE_UFIXED_POINT_16):value(v){}operator int()const{return value;}size_t bw()const{return 2;}const char* str()const{return "QNN_DATATYPE_UFIXED_POINT_16";}};
struct Tensor {int tensor=QNN_DATATYPE_UFIXED_POINT_16;DataType dtype;struct Grid {double scale;int32_t offset;};std::vector<Grid> quantParam{{SCALE,OFFSET}};struct Dims {size_t getNumElements()const{return ROWS*VOCAB;}}dims;};
}
struct Tensor {std::vector<float> logits;void* data=nullptr;size_t size=0;void setData(void*p){data=p;}void setDataType(int){}void setSize(size_t n){size=n;}};
struct InferenceStep {int variant=128,ctx_size=4096,n_past=0,n_process=0;std::string str()const{return "synthetic-final";}};
enum class LayerType {OUTPUT};
enum class ModelArchitectureType {DECODER,ENCODER};
struct Graph {QnnUtils::Tensor tensor;QnnUtils::Tensor* getOutput(const std::string&){return &tensor;}};
struct GraphEntry {Graph graph;Graph* operator()(int a,int c){assert(a==128&&c==4096);return &graph;}};
struct KV {int n_past(){return 0;}int n_valid_kv(){return 0;}};
struct AttentionMask {template<class... T> AttentionMask(T&&...){}};
struct OriginalDequant {
@ORIGINAL_DEQUANT@
};
class QnnNspModel:public OriginalDequant {
 public:
 size_t m_vocab_size=VOCAB,m_embd_size=1536,m_embeddingBufferSize=3072;
 ModelArchitectureType m_modelArchitectureType=ModelArchitectureType::DECODER;
 bool m_pooled_output=false,token_history_enabled=true;
 size_t _offset_to_apply_kv_prefix=0,_size_to_skip_kv_prefix=0;
 std::vector<int32_t> token_history;KV kv;KV* m_kvmanager=&kv;
 std::vector<GraphEntry> m_nsp_graphs{1};std::map<LayerType,std::string> m_layerNames{{LayerType::OUTPUT,"logits"}};
 bool failed(){return false;}std::string error(){return {};}
 void* getBuffer(QnnUtils::Tensor*,bool,uint32_t index){assert(index==0);return raw_rows.data();}
 void getEmbeddings(std::span<float>,InferenceStep&,uint32_t){std::abort();}
 template<class U,class T> void castOutputs(U*,std::span<T>&,size_t,uint32_t){std::abort();}
 template<class U,class T> void deQuantizeOutputs(U* p,std::span<T>& out,double scale,int32_t offset,size_t count){
  ++dequant_calls;assert(dequant_calls==1&&count==VOCAB);
  assert(reinterpret_cast<const void*>(p)==reinterpret_cast<const void*>(raw_rows.data()+8*VOCAB));
  auto& state=gemma_prefill_capture::state();capture_seen_before_dequant=state.captures==129;
  assert(capture_seen_before_dequant==expect_capture);
  if(expect_capture){
   std::ifstream f(std::string(getenv("GEMMA_PREFILL_CAPTURE_DIR"))+"/15-output-logits.raw",std::ios::binary);
   std::vector<uint16_t> observed(VOCAB);f.read(reinterpret_cast<char*>(observed.data()),VOCAB*2);assert(f.gcount()==VOCAB*2);
   assert(std::equal(observed.begin(),observed.end(),raw_rows.begin()+8*VOCAB));
  }
  OriginalDequant::deQuantizeOutputs(p,out,scale,offset,count); // original template body, unchanged, once
 }
@MODEL_DECLS@
};
struct Stats {void update(size_t){}};
class NspEngine {
 public:
 QnnNspModel* _model;struct {Stats process;} _kpis;
 explicit NspEngine(QnnNspModel*m):_model(m){}bool load(){return false;}
@ENGINE_DECLS@
};
@MODEL_ENTRY@
@GET_DEQUANT@
@ENGINE_PROCESS@
@ENGINE_PROCESS_ALL@
static uint64_t hash_raw(){uint64_t h=1469598103934665603ULL;for(uint16_t v:raw_rows){h^=v;h*=1099511628211ULL;}return h;}
int main(int argc,char**argv){
 assert(argc==3);expect_capture=argv[2][0]=='1';setenv("GEMMA_PREFILL_CAPTURE_DIR",argv[1],1);
 // Seed ONLY the prior payload budget counters, not fake input files or a completed input journal.
 auto& s=gemma_prefill_capture::state();s.captures=128;s.bytes=65536000;
 raw_rows.resize(ROWS*VOCAB);for(size_t r=0;r<ROWS;++r)for(size_t i=0;i<VOCAB;++i)raw_rows[r*VOCAB+i]=uint16_t(r*512+(i%512));
 uint64_t before=hash_raw();QnnNspModel model;NspEngine engine(&model);Tensor logits;
 std::vector<uint8_t> embeddings(1929*3072),perlayer(1929*17920);
 const unsigned request_cap=1;assert(request_cap==1);
 // REAL NspEngine PLE process -> processAll -> legacy runInference entry/final dispatch -> getDequantLogits.
 assert(engine.process(embeddings,perlayer,{},logits,false)==1);
 assert(dequant_calls==1&&synthetic_backend_calls==1&&logits.size==VOCAB&&logits.data==logits.logits.data());
 assert(hash_raw()==before);
 for(size_t i=0;i<VOCAB;++i){float expected=float((int32_t(raw_rows[8*VOCAB+i])+OFFSET)*SCALE);assert(logits.logits[i]==expected);}
 // Stand-in for the downstream sampler; original engine must return the unchanged F32 vector first.
 for(unsigned i=0;i<request_cap;++i){++sampler_calls;assert(dequant_calls==1);assert((s.captures==129)==expect_capture);}
 assert(sampler_calls==1);
 std::ofstream f(std::string(argv[1])+"/dequant.float32",std::ios::binary);f.write(reinterpret_cast<const char*>(logits.logits.data()),VOCAB*4);f.close();
 printf("legacy_PLE_dispatch=1 cap=1 final_n_past=1920 final_n_process=9 row=8 raw_values=262144 original_dequant_calls=%u sampler_calls=%u capture_before_dequant=%u raw_unchanged=1\n",dequant_calls,sampler_calls,capture_seen_before_dequant);
}
'''


def function(text,anchor):
    if text.count(anchor)!=1:raise ValueError('fixture function anchor changed')
    start=text.index(anchor);end=text.index('\n}',start)+2
    return text[start:end]


def build_fixture(out):
    if sha(BASE/REL)!=EXPECTED or sha(Q/'engines/qnn-htp.cpp')!=ENGINE_SHA or sha(Q/'engines/qnn-htp/nsp-base-model.hpp')!=BASE_HEADER_SHA:raise ValueError('actual source binding changed')
    engine=(Q/'engines/qnn-htp.cpp').read_text();source=(BASE/REL).read_text();header=(Q/'engines/qnn-htp/nsp-base-model.hpp').read_text()
    process=function(engine,'size_t NspEngine::process(std::vector<uint8_t>& embeddings,\n                          std::vector<uint8_t>& embeddings_perlayer,\n                          const std::vector<int32_t>& attention_map,\n                          Tensor& logits,')
    process_all=function(engine,'size_t NspEngine::processAll(const std::vector<int32_t>& tokens,\n                             std::vector<uint8_t>& embeddings,\n                             std::vector<uint8_t>& embeddings_perlayer,')
    legacy=function(source,'size_t QnnNspModel::runInference(const std::vector<int32_t>& tokens,\n                                 std::vector<uint8_t>& embedding,\n                                 std::vector<uint8_t>& embeddings_perlayer,\n                                 const std::vector<void*>* featureVector,\n                                 const std::vector<int32_t>& selected,\n                                 uint32_t start_idx,\n                                 bool post_update,\n                                 const std::vector<int32_t>& attention_map,\n                                 std::vector<float>& output,')
    start=legacy.index('  // Loop over each planned iteration');end=legacy.index('  // If only the last output is required')
    synthetic='''  // FIXTURE-ONLY synthetic backend replaces QNN execution, not the entry/final dispatch.
  ++synthetic_backend_calls;assert(n_inputs==1929&&!embeddings_perlayer.empty()&&!output_all);
  InferenceStep step;uint32_t buf_idx=0;unsigned chunks=0;
  for(size_t pos=0;pos<n_inputs;pos+=128){step.n_past=int(pos);step.n_process=int(std::min(size_t(128),n_inputs-pos));++chunks;}
  assert(chunks==16&&step.n_past==1920&&step.n_process==9);
'''
    legacy_fixture=legacy[:start]+synthetic+legacy[end:]
    dqstart=header.index('  template <typename U, typename T>\n  inline void deQuantizeOutputs(');dqend=header.index('\n  }',dqstart)+4;original_dequant=header[dqstart:dqend]
    out.mkdir(parents=True,exist_ok=False);includes=out/'headers/qualla';includes.mkdir(parents=True);shutil.copyfile(TRACK/'tools/prefill_capture.hpp',includes/'prefill_capture.hpp')
    json_header=next(BASE.rglob('nlohmann/json.hpp'),None)
    if json_header is None:
        # copytree has materialized the SDK include symlink; follow explicit walk as well.
        json_header=next((Path(p)/'json.hpp' for p,_,fs in os.walk(BASE,followlinks=True) if Path(p).name=='nlohmann' and 'json.hpp' in fs),None)
    if json_header is None:raise ValueError('bound nlohmann header absent')
    variants={};bindings={'engine_process':hashlib.sha256(process.encode()).hexdigest(),'engine_processAll':hashlib.sha256(process_all.encode()).hexdigest(),'original_legacy_runInference':hashlib.sha256(legacy.encode()).hexdigest(),'original_dequant_template':hashlib.sha256(original_dequant.encode()).hexdigest(),'NN_loop_replacement':'synthetic backend only; actual entry/output sizing/final dispatch retained','sampler':'downstream fixture stand-in; no sampler implementation/fidelity claim'}
    stage=TRACK/'.local/frozen-stages/paired-mapping-observer-stage-01';cfg=json.loads((stage/'gemma4-e2b-htp-cl4096-greedy.json').read_text());assert cfg['dialog']['max-num-tokens']==1 and 'dialog setMaxNumTokens dialog1 1\n' in (stage/'exact-long.script').read_text()
    for name,text in [('original',source),('relocated',patch(source))]:
        get=function(text,'size_t QnnNspModel::getDequantLogits(')
        declarations=(legacy_fixture.split('{',1)[0].replace('QnnNspModel::','')+';\n'+get.split('{',1)[0].replace('QnnNspModel::','')+';')
        engine_decl=process.split('{',1)[0].replace('NspEngine::','')+';\n'+process_all.split('{',1)[0].replace('NspEngine::','')+';'
        cpp=STUB
        for marker,value in {'@ORIGINAL_DEQUANT@':original_dequant,'@MODEL_DECLS@':declarations,'@ENGINE_DECLS@':engine_decl,'@MODEL_ENTRY@':legacy_fixture,'@GET_DEQUANT@':get,'@ENGINE_PROCESS@':process,'@ENGINE_PROCESS_ALL@':process_all}.items():cpp=cpp.replace(marker,value)
        path=out/(name+'.cpp');path.write_text(cpp);binary=out/name;cmd=['g++','-std=c++20','-O1','-pthread','-I'+str(out/'headers'),'-I'+str(json_header.parent.parent),str(path),'-o',str(binary)]
        (out/(name+'-command.json')).write_text(json.dumps(cmd,indent=2)+'\n');p=subprocess.run(cmd,capture_output=True,timeout=60);(out/(name+'-compile.stdout')).write_bytes(p.stdout);(out/(name+'-compile.stderr')).write_bytes(p.stderr)
        if p.returncode:raise RuntimeError('fixture compilation failed; see private retained stderr')
        run=out/(name+'-run');run.mkdir();p=subprocess.run([str(binary),str(run),'1' if name=='relocated' else '0'],capture_output=True,timeout=30);(run/'stdout.txt').write_bytes(p.stdout);(run/'stderr.txt').write_bytes(p.stderr)
        if p.returncode:raise RuntimeError('fixture execution failed '+str(p.returncode))
        records=[json.loads(s) for s in (run/'capture.jsonl').read_text().splitlines()];variants[name]={'exit':p.returncode,'summary':p.stdout.decode().strip(),'capture_records':len(records),'dequant_F32_sha256':sha(run/'dequant.float32')}
        if name=='original':assert not records and not (run/'15-output-logits.raw').exists()
        else:
            assert len(records)==2 and [r['event'] for r in records]==['begin','complete'];r=records[-1];assert r['final_valid_row']==8 and r['shape']==[1,1,262144] and r['bytes']==524288 and r['datatype']=='QNN_DATATYPE_UFIXED_POINT_16' and r['offset']==-31869 and r['scale']==0.0008891067700460553 and r['before_original_dequantization'] and r['row_view_already_offset'] and r['completed_payloads']==129 and r['total_payload_bytes']==66060288
            variants[name].update(raw_values_verified=262144,row8_selected_once=True,raw_payload_sha256=sha(run/'15-output-logits.raw'),grid_metadata_verified=True,capture_before_original_dequant=True)
    assert variants['original']['dequant_F32_sha256']==variants['relocated']['dequant_F32_sha256']
    result={'classification':'real_PLE_dispatch_with_synthetic_QNN_backend_fixture','variants':variants,'original_and_relocated_dequant_bit_identical':True,'config_and_script_cap1_verified':True,'request_sampler_calls':1,'original_dequant_call_count':1,'actual_engine_dispatch_and_getDequant_source_compiled':True,'full_QNN_loop_or_model_executed':False,'real_sampler_executed':False,'phone_executed':False,'prior_input_capture_budget_counters_seeded_only':True};(out/'source-bindings.json').write_text(json.dumps(bindings,indent=2)+'\n');(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/paired-legacy-logits'):p.error('owned fresh fixture directory required')
    build_fixture(out)

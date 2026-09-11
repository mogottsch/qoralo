#!/usr/bin/env python3
"""Create a source-only one-request aligned GPU reference; NEVER builds or runs it.

Keep canonical0025 source/results and every QNN byte untouched. Remove only the
renderer-owned BOS on LiteRT; its existing metadata-owned BOS remains. Compare
ALL actual preprocessed IDs to the frozen1929 IDs before any RunPrefill.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

TRACK=Path(__file__).resolve().parents[1]
EXP=TRACK.parents[1]
REFERENCE=EXP.parent/'0025-gemma-4-e2b-it-android'
SOURCE=REFERENCE/'tools/litert_lm_canonical_runner.cc'
SOURCE_SHA='5148aec25a39178224e6765e63ff448d27211375d83d394739c7182afc74ba59'
STAGE=TRACK/'.local/frozen-stages/selected-id-long-20260911T143756Z-01'
INPUT_SHA='3b5c04febbc9d55c529ee7ece510607203dbdc8256a6abc05ba0498cf4e52b64'


def sha(data):return hashlib.sha256(data).hexdigest()


def patch(source,ids):
    if sha(source.encode())!=SOURCE_SHA:raise ValueError('maintained canonical source changed; stale private build-tree source is not accepted')
    if len(ids)!=1929 or sha(struct.pack('<1929i',*ids))!=INPUT_SHA:raise ValueError('wrong frozen effective input')
    original=source;changes=[]
    def replace(before,after,count=1):
        nonlocal source
        if source.count(before)!=count:raise ValueError('source anchor count mismatch: '+before[:80])
        source=source.replace(before,after);changes.append((before,after,count))
    replace('// Experiment 0025 canonical Android LLM benchmark runner.',
            '// Source-only0031 aligned-reference derivative; exactly one GPU long request, not a campaign.')
    replace('ABSL_FLAG(std::string, backend, "cpu",','ABSL_FLAG(std::string, backend, "gpu",')
    replace('gemma4-no-tools-no-thinking-system-user-v1','gemma4-single-runtime-bos-aligned-reference-v1')
    replace('return "<bos><|turn>system\\n" + system','return "<|turn>system\\n" + system')
    declaration='const std::vector<int> kExpectedAlignedInputIds = {'+','.join(map(str,ids))+'};\n'
    anchor='struct MemorySnapshot {'
    replace(anchor,'// Frozen actual QNN input, int32le SHA256 '+INPUT_SHA+'\n'+declaration+'\n'+anchor)
    before='''  const bool rewind_called = current_step != 0;
  if (rewind_called) {
    ABSL_RETURN_IF_ERROR(session.RewindToStep(0));
  }'''
    replace(before,'''  const bool rewind_called = false;
  if (current_step != 0) return absl::FailedPreconditionError("aligned reference requires a fresh step-zero Session; no rewind/replay");''')
    before='''  std::vector<InputData> input;
  input.emplace_back(InputText(rendered_prompt));
  ABSL_RETURN_IF_ERROR(session.RunPrefill(input));'''
    after='''  ABSL_ASSIGN_OR_RETURN(auto actual_input_ids,
      GetEffectiveTokenIds(engine, session.GetSessionConfig(), rendered_prompt));
  const bool alignment_matches = actual_input_ids == kExpectedAlignedInputIds;
  const Json alignment = {
      {"actual_effective_token_ids", actual_input_ids},
      {"expected_effective_token_ids", kExpectedAlignedInputIds},
      {"all_ids_equal", alignment_matches},
      {"expected_int32le_sha256", "'''+INPUT_SHA+'''"},
      {"prefill_not_yet_started", true},
      {"basis", "Actual session preprocessing, not just a count or rendered-text comparison"}};
  ABSL_RETURN_IF_ERROR(WriteFile(output_dir / "input-alignment-before-prefill.json", alignment.dump(2) + "\\n"));
  if (!alignment_matches) return absl::FailedPreconditionError("effective input mismatch: full IDs retained; no neural request was submitted");
  std::vector<InputData> input;
  input.emplace_back(InputText(rendered_prompt));
  ABSL_RETURN_IF_ERROR(session.RunPrefill(input));'''
    replace(before,after)
    replace('for (const std::string tier : {"short", "medium", "long"})',
            'for (const std::string tier : {"long"})')
    anchor='  const std::string model_path = absl::GetFlag(FLAGS_model_path);'
    guard='''  if (absl::GetFlag(FLAGS_backend) != "gpu" ||
      absl::GetFlag(FLAGS_max_num_tokens) != 8192 ||
      absl::GetFlag(FLAGS_max_output_tokens) != 2048 ||
      absl::GetFlag(FLAGS_request_timeout_seconds) != 1800 ||
      absl::GetFlag(FLAGS_num_cpu_threads) != 4 ||
      absl::GetFlag(FLAGS_cache_dir).empty() || absl::GetFlag(FLAGS_cache_dir) == ":nocache" ||
      absl::GetFlag(FLAGS_smoke_only) || absl::GetFlag(FLAGS_reset_probe_only) ||
      absl::GetFlag(FLAGS_reset_mode) != "fresh_session") {
    return absl::InvalidArgumentError("one aligned GPU long/8192-context/max2048/1800s/4-CPU-thread reference only; no alternate scope");
  }
'''
    replace(anchor,guard+anchor)
    start=source.index('  if (absl::GetFlag(FLAGS_smoke_only) &&')
    end=source.index('\n  Json result = {',start)
    block=source[start:end]
    if block.count('RunRequest(')!=5:raise ValueError('old campaign/probe branching changed')
    single='''  ABSL_ASSIGN_OR_RETURN(Json run,
      RunRequest(*engine, *session, workloads[0].second, "long",
                 "aligned-reference-long-01", "aligned_reference",
                 2048, 1800, kExpectedAlignedInputIds.size(), output_dir));
  annotate_isolation(&run, "setup_created_fresh_session_one_aligned_request",
                     initial_session_creation_seconds, true);
  runs.push_back(std::move(run));
  ABSL_RETURN_IF_ERROR(persist_checkpoint());
'''
    replace(block,single)
    replace('{"experiment", "0025-gemma-4-e2b-it-android"}',
            '{"experiment", "0031-aligned-reference-diagnostic"}',2)
    replace('CPU TOP_P(k=1,p=1) exact argmax implementation for both CPU and GPU neural backends',
            'Unchanged CPU TOP_P(k=1,p=1,temp=1); intended singleton argmax, ties/numerical parity unproven')
    reverse=source
    for before,after,count in reversed(changes):
        if reverse.count(after)!=count:raise ValueError('inverse anchor is ambiguous')
        reverse=reverse.replace(after,before)
    assert reverse==original
    assert source.count('RunRequest(')==2  # definition and ONE call
    assert source.count('session.RunPrefill(input)')==1
    return source,[{'before_sha256':sha(a.encode()),'after_sha256':sha(b.encode()),'count':n} for a,b,n in changes]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();out=args.output_dir.resolve()
    if not out.is_relative_to((TRACK/'.local/aligned-reference-readiness').resolve()):p.error('fresh private source-readiness directory required')
    data=(STAGE/'token-ids/long.int32le').read_bytes();ids=struct.unpack('<1929i',data)
    text,changes=patch(SOURCE.read_text(),ids)
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    cpp=out/'litert_lm_aligned_reference.cc';cpp.write_text(text)
    (out/'expected-input-ids.json').write_text(json.dumps(list(ids))+'\n')
    result={'classification':'source_ready_not_compiled_not_phone_ready','source_sha256':SOURCE_SHA,
      'derivative_sha256':sha(text.encode()),'frozen_input_int32le_sha256':INPUT_SHA,
      'expected_tokens':1929,'planned_neural_requests':1,'backend':'gpu','context_capacity':8192,'max_output_tokens':2048,
      'changes_count':len(changes),'inverse_reconstruction_exact':True,'changes':changes,
      'model_build_load_or_inference':False,'adb_calls':0,
      'limits':'New diagnostic frontend, not commercial/source runtime equivalence. Same reference bundle and LiteRTv0.16.1 core/library identities must be independently bound before a future run. Source is not compiled/ABI-validated yet.'}
    (out/'preparation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

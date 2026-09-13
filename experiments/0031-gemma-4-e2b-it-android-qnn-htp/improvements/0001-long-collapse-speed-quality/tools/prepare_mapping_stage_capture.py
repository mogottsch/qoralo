#!/usr/bin/env python3
"""HOST-ONLY observation preparation: LUT mmap result/timing and pointer validity."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

TRACK=Path(__file__).resolve().parents[1]
BASE=TRACK/'.local/paired-allocation-observer/build-01/sdk-source'
CPP='examples/Genie/Genie/src/qualla/'
EXPECTED={'MmappedFile/src/MmappedFile.cpp':'c4a09da29577ee6af2d2b93fc016bbf5ee44b54a0651bcc8f99a766fd977530a','encoders/text-encoders/LUT.cpp':'adfffb77f5c69af043f4de23878c96b5dcbf2a285eda0b192990c4dc44557b9e'}


def replace(text,old,new,count=1):
    if text.count(old)!=count:raise ValueError('mapping source anchor changed')
    after=text.replace(old,new)
    if after.replace(new,old)!=text:raise ValueError('mapping observation not invertible')
    return after


def patch_mmap(source):
    old='    addr = mmap(nullptr, static_cast<size_t>(size), prot, flags, m_fileDescriptor, {});'
    new='''    const char* observed_role = gemma_mapping_trace::role(m_filename.c_str());
    gemma_mapping_trace::emit(observed_role, "mmap.before", true, size, false, nullptr, 0,
                             false, false, false, false, 0, errno);
'''+old+'''
    const int errno_immediately_after_mmap = errno;
    gemma_mapping_trace::emit(observed_role, "mmap.after", true, size, true, addr,
                             (addr == MAP_FAILED || addr == nullptr) ? 0 : size,
                             false, false, false, false, 0, errno_immediately_after_mmap);'''
    out=replace(source,old,new)
    start=out.index('bool File::open(bool readwrite, uint64_t overrideSize) {')
    end=out.index('\nbool File::unmapInternal()',start)
    old_block=out[start:end];block=old_block
    opening='bool File::open(bool readwrite, uint64_t overrideSize) {'
    intro='''
  const auto observed_open_return = [&](bool actual, bool request_known, uint64_t requested) {
    const int errno_at_open_return = errno;
    gemma_mapping_trace::emit(gemma_mapping_trace::role(m_filename.c_str()), "file.open.return",
                             request_known, requested, true, m_address, m_size,
                             true, actual, true, isOpen(), 0, errno_at_open_return);
    return actual;
  };'''
    block=replace(block,opening,opening+intro)
    block=replace(block,'return false;','return observed_open_return(false, false, overrideSize);',4)
    block=replace(block,'  return true;','  return observed_open_return(true, true, (overrideSize != 0) ? overrideSize : openedSize);')
    out=out[:start]+block+out[end:]
    return '#include "qualla/mapping_stage_trace.hpp"\n'+out


def patch_lut(source):
    old='''    embeddingLut     = embeddingFile->mutableData();
    embeddingLutSize = fileSize;'''
    new=old+'''
    const int errno_at_lut_binding = errno;
    gemma_mapping_trace::emit(gemma_mapping_trace::role(embedding_file_path.c_str()), "lut.cached",
                             true, fileSize, true, embeddingLut, embeddingFile->size(),
                             false, false, true, embeddingFile->isOpen(), embeddingLutSize,
                             errno_at_lut_binding);'''
    return '#include "qualla/mapping_stage_trace.hpp"\n'+replace(source,old,new)


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def prepare(out):
    result=json.loads((BASE.parent/'build-result.json').read_text())
    if result['actual_native_exit']!=0 or result['binary_sha256']!='87f8b9b624d9de6e08de372740e5814fc64eb352c68b2c73fd07c8190e41d9eb':raise ValueError('allocation-runtime base mismatch')
    for name,expected in EXPECTED.items():
        if sha(BASE/(CPP+name))!=expected:raise ValueError('mapping source changed '+name)
    files=[Path(parent)/name for parent,_,names in os.walk(BASE,followlinks=True) for name in names if (Path(parent)/name).is_file()]
    if sum(f.stat().st_size for f in files)>2*1024**3 or shutil.disk_usage(TRACK).free<72*1024**3:raise ValueError('copy/disk bound')
    out.mkdir(parents=True,exist_ok=False);dest=out/'sdk-source';shutil.copytree(BASE,dest,symlinks=False);changes=[]
    for name,fn in [('MmappedFile/src/MmappedFile.cpp',patch_mmap),('encoders/text-encoders/LUT.cpp',patch_lut)]:
        rel=CPP+name;(dest/rel).write_text(fn((BASE/rel).read_text()));changes.append({'path':rel,'before':sha(BASE/rel),'after':sha(dest/rel)})
    header=dest/(CPP+'include/qualla/mapping_stage_trace.hpp');shutil.copyfile(TRACK/'tools/mapping_stage_trace.hpp',header);changes.append({'path':str(header.relative_to(dest)),'before':None,'after':sha(header)})
    evidence={'classification':'mapping_observation_source_only','changes':changes,'model_or_phone_executed':False,'original_mmap_call_and_flags_unchanged':True,'File_open_return_behavior_unchanged':True,'AS_model_dtype_caps_unchanged':True,'scope':'Only exact main/PLE LUT basenames; syscall before/after plus File.open and cached LUT validity','errno':'Immediately after original mmap before diagnostics; caller errno restored','allocation_free_log_cap':{'events':32,'bytes':32768}}
    (out/'preparation.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=a.output_dir.resolve()
    if not out.is_relative_to(TRACK/'.local/paired-mapping-observer'):p.error('fresh owned private root required')
    prepare(out)

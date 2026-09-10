"""One controlled AXML declaration insertion; no code/resource/native recompilation."""
from __future__ import annotations
from copy import deepcopy
import struct

LIBRARY = 'libcdsprpc.so'
ANDROID = 'http://schemas.android.com/apk/res/android'


def need(condition, message):
    if not condition: raise ValueError(message)


def chunks(data):
    need(len(data) >= 8 and struct.unpack_from('<HHI', data) == (3, 8, len(data)), 'invalid binary XML root')
    result=[]; offset=8
    while offset < len(data):
        need(offset+8 <= len(data), 'truncated XML chunk')
        kind, header, size=struct.unpack_from('<HHI',data,offset)
        need(size >= header >= 8 and offset+size <= len(data), 'invalid XML chunk size')
        result.append((kind,data[offset:offset+size]));offset+=size
    return result


def strings(pool):
    kind,header,size,count,styles,flags,start,style_start=struct.unpack_from('<HHIIIIII',pool)
    need(kind==1 and header==28 and not styles and not style_start and flags==0, 'requires reviewed style-free UTF-16 pool')
    need(start==28+count*4 and start <= len(pool), 'invalid string offsets')
    result=[]
    for i in range(count):
        offset=start+struct.unpack_from('<I',pool,28+i*4)[0]
        length=struct.unpack_from('<H',pool,offset)[0];offset+=2
        if length & 0x8000:
            length=((length&0x7fff)<<16)|struct.unpack_from('<H',pool,offset)[0];offset+=2
        need(offset+length*2+2<=len(pool) and pool[offset+length*2:offset+length*2+2]==b'\0\0','invalid UTF-16 string')
        result.append(pool[offset:offset+length*2].decode('utf-16le'))
    return result


def append_string(pool, value):
    values=strings(pool);need(value not in values,'new library already in string pool')
    count=len(values);start=struct.unpack_from('<I',pool,20)[0]
    encoded=struct.pack('<H',len(value))+value.encode('utf-16le')+b'\0\0'
    payload=pool[start:]+encoded
    payload+=b'\0'*((-len(payload))%4)
    header=bytearray(pool[:28]);struct.pack_into('<I',header,8,count+1);struct.pack_into('<I',header,20,start+4)
    result=header+pool[28:start]+struct.pack('<I',len(pool)-start)+payload
    struct.pack_into('<I',result,4,len(result))
    need(strings(result)==values+[value],'string pool preservation failed')
    return bytes(result),count


def node(chunk, values):
    ns,name,attribute_start,attribute_size,count=struct.unpack_from('<IIHHH',chunk,16)
    need(attribute_size==20 and 16+attribute_start+count*20<=len(chunk),'unsupported attributes')
    text=lambda i:None if i==0xffffffff else values[i]
    attrs=[]
    for i in range(count):
        pos=16+attribute_start+i*20
        a_ns,a_name,raw,length,zero,kind,value=struct.unpack_from('<IIIHBBI',chunk,pos)
        need(length==8 and zero==0,'invalid typed attribute')
        attrs.append({'namespace':text(a_ns),'name':text(a_name),'raw':text(raw),'type':kind,
                      'value':text(value) if kind==3 else value})
    return {'namespace':text(ns),'name':text(name),'attributes':attrs,'children':[]}


def tree(data):
    parts=chunks(data);pools=[p for k,p in parts if k==1];need(len(pools)==1,'one string pool required')
    values=strings(pools[0]);stack=[];root=None
    for kind,part in parts:
        if kind==0x102:
            current=node(part,values)
            if stack:stack[-1]['children'].append(current)
            else:need(root is None,'multiple roots');root=current
            stack.append(current)
        elif kind==0x103:
            need(stack,'unbalanced XML');ns,name=struct.unpack_from('<II',part,16)
            need(stack[-1]['name']==values[name],'wrong closing tag');stack.pop()
        else:need(kind in (1,0x180,0x100,0x101),'unexpected binary XML chunk')
    need(root is not None and not stack,'incomplete XML')
    return root


def declaration(parent, name):
    return [child for child in parent['children'] if child['name']=='uses-native-library' and
            any(a['namespace']==ANDROID and a['name']=='name' and a['value']==name for a in child['attributes'])]


def patch_manifest(data):
    before=tree(data);application=next(n for n in before['children'] if n['name']=='application')
    need(not declaration(application,LIBRARY),'library already declared')
    parts=chunks(data);pool_index=next(i for i,(k,_) in enumerate(parts) if k==1)
    values=strings(parts[pool_index][1]);template=None
    for i,(kind,part) in enumerate(parts):
        if kind!=0x102:continue
        current=node(part,values)
        if current['name']=='uses-native-library' and any(a['name']=='name' and a['value']=='libOpenCL.so' for a in current['attributes']):
            need(i+1<len(parts) and parts[i+1][0]==0x103,'template must be empty declaration')
            need(any(a['namespace']==ANDROID and a['name']=='required' and a['type']==0x12 and a['value']==0 for a in current['attributes']),'template must be optional')
            template=i;break
    need(template is not None,'reviewed optional OpenCL template missing')
    new_pool,new_index=append_string(parts[pool_index][1],LIBRARY)
    changed=bytearray(parts[template][1]);attribute_start,attribute_size,count=struct.unpack_from('<HHH',changed,24)
    replacements=0
    for i in range(count):
        pos=16+attribute_start+i*attribute_size
        ns,name,raw=struct.unpack_from('<III',changed,pos)
        if values[ns]==ANDROID and values[name]=='name':
            need(changed[pos+15]==3,'library name must be string')
            if raw!=0xffffffff:struct.pack_into('<I',changed,pos+8,new_index)
            struct.pack_into('<I',changed,pos+16,new_index);replacements+=1
    need(replacements==1,'expected one library name attribute')
    parts[pool_index]=(1,new_pool)
    parts[template+2:template+2]=[(0x102,bytes(changed)),parts[template+1]]
    body=b''.join(p for _,p in parts);result=struct.pack('<HHI',3,8,8+len(body))+body
    after=tree(result);after_app=next(n for n in after['children'] if n['name']=='application')
    added=declaration(after_app,LIBRARY);need(len(added)==1,'one declaration required')
    required=[a for a in added[0]['attributes'] if a['namespace']==ANDROID and a['name']=='required']
    need(len(required)==1 and required[0]['type']==0x12 and required[0]['value']==0,'required must remain false')
    restored=deepcopy(after);restored_app=next(n for n in restored['children'] if n['name']=='application')
    restored_app['children'].remove(declaration(restored_app,LIBRARY)[0])
    need(restored==before,'unexpected manifest semantic delta')
    return result,{'library':LIBRARY,'required':False,'soleSemanticDelta':'one application uses-native-library declaration',
                   'originalManifestTree':before,'newManifestTree':after}

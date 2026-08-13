package dev.moket.ttsbench;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;

/** JVM-testable adapter from the pinned, flat deployment JSON to sherpa's Java builders. */
public record SherpaConfig(String modelType, Map<String,String> modelValues,
        String ruleFsts, String ruleFars, String referenceAudio, String referenceText,
        String language, int numSteps) {
    private static final Map<String,List<String>> PATH_KEYS=Map.of(
        "pocket",List.of("lm_flow","lm_main","encoder","decoder","text_conditioner","vocab_json","token_scores_json"),
        "kokoro",List.of("model","voices","tokens","lexicon","data_dir","dict_dir"),
        "supertonic",List.of("duration_predictor","text_encoder","vector_estimator","vocoder","tts_json","unicode_indexer","voice_style"));
    private static final Map<String,List<String>> OPTIONAL=Map.of(
        "pocket",List.of(), "kokoro",List.of("lexicon","data_dir","dict_dir"), "supertonic",List.of());

    public static SherpaConfig parse(File file,Map<String,File> verified)throws IOException{
        String json=new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8);
        String type=required(json,"model_type");
        List<String> keys=PATH_KEYS.get(type);if(keys==null)throw new IOException("unsupported model_type: "+type);
        Map<String,String> values=new LinkedHashMap<>();
        for(String key:keys){String relative=optional(json,key,null);if(relative==null&&OPTIONAL.get(type).contains(key))continue;if(relative==null)throw new IOException("missing "+key);values.put(key,verifiedPath(verified,relative,key));}
        String lang=optional(json,"lang",null);
        String fsts=pathList(verified,optional(json,"rule_fsts",null),"rule_fsts");
        String fars=pathList(verified,optional(json,"rule_fars",null),"rule_fars");
        String ref=optional(json,"reference_audio",null);if(ref!=null)ref=verifiedPath(verified,ref,"reference_audio");
        return new SherpaConfig(type,Map.copyOf(values),fsts,fars,ref,optional(json,"reference_text",null),lang,optionalInt(json,"num_steps",5));
    }
    private static String pathList(Map<String,File> verified,String value,String key)throws IOException{
        if(value==null||value.isBlank())return "";StringJoiner out=new StringJoiner(",");for(String p:value.split(","))out.add(verifiedPath(verified,p.trim(),key));return out.toString();
    }
    private static String verifiedPath(Map<String,File> verified,String relative,String key)throws IOException{
        File f=verified.get(relative);if(f!=null)return f.getAbsolutePath();
        // Frontend data_dir/dict_dir are directories, while the signed inventory contains
        // their individual regular files. Resolve a directory only through a verified child.
        String prefix=relative.endsWith("/")?relative:relative+"/";
        for(var e:verified.entrySet())if(e.getKey().startsWith(prefix)){
            Path candidate=e.getValue().toPath();int childParts=Paths.get(e.getKey().substring(prefix.length())).getNameCount();
            for(int i=0;i<childParts;i++)candidate=candidate.getParent();
            if(candidate!=null&&Files.isDirectory(candidate)&&candidate.getFileName().toString().equals(Paths.get(relative).getFileName().toString()))return candidate.toFile().getAbsolutePath();
        }
        throw new IOException(key+" is not in verified inventory: "+relative);
    }
    private static String required(String json,String key)throws IOException{String v=optional(json,key,null);if(v==null)throw new IOException("missing "+key);return v;}
    private static String optional(String json,String key,String fallback){Matcher m=Pattern.compile("\\\""+Pattern.quote(key)+"\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"").matcher(json);return m.find()?m.group(1):fallback;}
    private static int optionalInt(String json,String key,int fallback)throws IOException{Matcher m=Pattern.compile("\\\""+Pattern.quote(key)+"\\\"\\s*:\\s*(\\d+)").matcher(json);if(!m.find())return fallback;try{return Integer.parseInt(m.group(1));}catch(NumberFormatException e){throw new IOException("bad "+key,e);}}
}

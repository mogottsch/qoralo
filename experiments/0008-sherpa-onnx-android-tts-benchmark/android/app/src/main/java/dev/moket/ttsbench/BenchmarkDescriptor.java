package dev.moket.ttsbench;

import java.util.*;
import java.util.regex.*;

/** Immutable, deliberately small launch descriptor. Model-specific sherpa JSON remains a verified file. */
public record BenchmarkDescriptor(String candidate, String transcript, String transcriptSha256,
        String sherpaConfigPath, Map<String,String> files, String provider, int numThreads,
        int warmRuns, int speakerId, String language) {
    public BenchmarkDescriptor {
        Objects.requireNonNull(candidate); Objects.requireNonNull(transcript); Objects.requireNonNull(transcriptSha256);
        Objects.requireNonNull(sherpaConfigPath); files = Map.copyOf(files); Objects.requireNonNull(provider);
        if (!provider.equals("cpu")) throw new IllegalArgumentException("provider must be cpu");
        if (numThreads != 1 && numThreads != 2) throw new IllegalArgumentException("threads must be 1 or 2");
        if (warmRuns < 3) throw new IllegalArgumentException("at least three warm runs required");
        if (!transcriptSha256.matches("[0-9a-f]{64}")) throw new IllegalArgumentException("bad transcript hash");
        if (candidate.isBlank() || language==null || language.isBlank()) throw new IllegalArgumentException("candidate/language must be non-empty");
        if (files.isEmpty()) throw new IllegalArgumentException("empty deployed file inventory");
        for (var e : files.entrySet()) if (e.getKey()==null || e.getKey().isBlank() || e.getValue()==null || !e.getValue().matches("[0-9a-f]{64}")) throw new IllegalArgumentException("bad inventory entry: " + e.getKey());
        if (!transcriptSha256.equals(files.get(transcript))) throw new IllegalArgumentException("transcript must be pinned by transcript_sha256");
        if (!files.containsKey(sherpaConfigPath)) throw new IllegalArgumentException("sherpa config must be pinned");
    }

    /** Parses the controlled runner format, not arbitrary JSON. Unknown fields are harmless. */
    public static BenchmarkDescriptor parse(String json) {
        String candidate = string(json, "candidate");
        String transcript = string(json, "transcript");
        String transcriptHash = string(json, "transcript_sha256");
        String config = string(json, "sherpa_config_path");
        String provider = string(json, "provider");
        int threads = integer(json, "num_threads");
        int warm = integer(json, "warm_runs");
        int sid = optionalInteger(json, "speaker_id", 0);
        String language = optionalString(json, "language", "en");
        Matcher body = Pattern.compile("\\\"files\\\"\\s*:\\s*\\{(.*?)\\}", Pattern.DOTALL).matcher(json);
        if (!body.find()) throw new IllegalArgumentException("missing files");
        Map<String,String> files = new LinkedHashMap<>();
        Matcher entry = Pattern.compile("\\\"([^\\\"]+)\\\"\\s*:\\s*\\\"([0-9a-f]+)\\\"").matcher(body.group(1));
        while (entry.find()) files.put(entry.group(1), entry.group(2));
        return new BenchmarkDescriptor(candidate, transcript, transcriptHash, config, files, provider, threads, warm, sid, language);
    }
    private static String string(String j,String k) { Matcher m=Pattern.compile("\\\""+Pattern.quote(k)+"\\\"\\s*:\\s*\\\"([^\\\"]*)\\\"").matcher(j); if(!m.find())throw new IllegalArgumentException("missing "+k); return m.group(1); }
    private static String optionalString(String j,String k,String d) { try{return string(j,k);}catch(IllegalArgumentException e){return d;} }
    private static int integer(String j,String k) { Matcher m=Pattern.compile("\\\""+Pattern.quote(k)+"\\\"\\s*:\\s*(-?\\d+)").matcher(j);if(!m.find())throw new IllegalArgumentException("missing "+k);return Integer.parseInt(m.group(1)); }
    private static int optionalInteger(String j,String k,int d) { try{return integer(j,k);}catch(IllegalArgumentException e){return d;} }
}

package dev.moket.kokorocompare;

import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;

/** Fixed-contract transcription of sherpa-onnx v1.13.5's Kokoro lexicon branch. */
final class KokoroFrontend {
    private static final Set<String> PUNCTUATION = Set.of(";", ":", ",", ".", "!", "?", "—", "…", "\"", "(", ")", "“", "”");
    private static final Set<String> SENTENCE_END = Set.of(".", "!", "?", ";");
    private final Map<String,Integer> tokenToId;
    private final Map<String,int[]> selectedLexicon;
    private final File voiceRaw;

    record Result(long[] tokenIds, float[] style, int styleIndex, List<String> parts, List<String> words) {}

    private KokoroFrontend(Map<String,Integer> tokenToId, Map<String,int[]> selectedLexicon, File voiceRaw) {
        this.tokenToId = tokenToId;
        this.selectedLexicon = selectedLexicon;
        this.voiceRaw = voiceRaw;
    }

    static KokoroFrontend load(File tokens, File lexicon, File voiceRaw, String text) throws Exception {
        Map<String,Integer> tokenMap = loadTokens(tokens);
        List<String> parts = splitAscii(text);
        Set<String> wanted = new HashSet<>();
        for (String part : parts) if (!PUNCTUATION.contains(part)) wanted.add(part.toLowerCase(Locale.ROOT));
        Map<String,int[]> selected = loadSelectedLexicon(lexicon, tokenMap, wanted);
        if (!selected.keySet().containsAll(wanted)) {
            Set<String> missing = new TreeSet<>(wanted); missing.removeAll(selected.keySet());
            throw new IOException("selected transcript has lexicon OOV words: " + missing);
        }
        if (voiceRaw.length() != 510L * 256L * Float.BYTES) throw new IOException("voice raw shape drift");
        return new KokoroFrontend(tokenMap, selected, voiceRaw);
    }

    Result convert(String text) throws Exception {
        List<String> parts = splitAscii(text);
        List<Long> current = new ArrayList<>(); current.add(0L);
        List<long[]> segments = new ArrayList<>();
        List<String> words = new ArrayList<>();
        for (String raw : parts) {
            String part = raw.toLowerCase(Locale.ROOT);
            if (PUNCTUATION.contains(part)) {
                Integer id = tokenToId.get(part);
                if (id == null) throw new IOException("punctuation token unavailable: " + part);
                current.add(id.longValue());
                if (SENTENCE_END.contains(part)) {
                    current.add(0L); segments.add(toLongArray(current)); current = new ArrayList<>(); current.add(0L);
                }
            } else {
                int[] pronunciation = selectedLexicon.get(part);
                if (pronunciation == null) throw new IOException("runtime lexicon OOV: " + part);
                words.add(part);
                for (int id : pronunciation) current.add((long)id);
                current.add(tokenToId.get(" ").longValue());
            }
        }
        if (current.size() > 1) { current.add(0L); segments.add(toLongArray(current)); }
        if (segments.size() != 1) throw new IOException("frozen route requires exactly one sentence segment");
        long[] ids = segments.get(0);
        int styleIndex = ids.length - 2;
        if (styleIndex != 123) throw new IOException("style index drift: " + styleIndex);
        float[] style = readStyleRow(voiceRaw, styleIndex);
        return new Result(ids, style, styleIndex, List.copyOf(parts), List.copyOf(words));
    }

    private static Map<String,Integer> loadTokens(File path) throws Exception {
        Map<String,Integer> result = new HashMap<>();
        int lineNumber = 0;
        for (String raw : Files.readAllLines(path.toPath(), StandardCharsets.UTF_8)) {
            lineNumber++;
            String[] fields = raw.trim().split("\\s+");
            String token; String value;
            if (fields.length == 1) { token = " "; value = fields[0]; }
            else if (fields.length == 2) { token = fields[0]; value = fields[1]; }
            else throw new IOException("malformed tokens line " + lineNumber);
            if (result.putIfAbsent(token, Integer.parseInt(value)) != null) throw new IOException("duplicate token");
        }
        if (!Objects.equals(result.get(" "), 16)) throw new IOException("space token drift");
        return result;
    }

    private static Map<String,int[]> loadSelectedLexicon(File path, Map<String,Integer> tokenMap, Set<String> wanted) throws Exception {
        Map<String,int[]> result = new HashMap<>();
        try (BufferedReader reader = Files.newBufferedReader(path.toPath(), StandardCharsets.UTF_8)) {
            for (String line; (line = reader.readLine()) != null;) {
                String[] fields = line.trim().split("\\s+");
                if (fields.length < 2) throw new IOException("malformed lexicon line");
                String word = fields[0].toLowerCase(Locale.ROOT);
                if (!wanted.contains(word) || result.containsKey(word)) continue; // first pronunciation wins
                int[] ids = new int[fields.length - 1];
                for (int i=1;i<fields.length;i++) {
                    Integer value = tokenMap.get(fields[i]);
                    if (value == null) throw new IOException("lexicon uses unknown token: " + fields[i]);
                    ids[i-1] = value;
                }
                result.put(word, ids);
            }
        }
        return result;
    }

    private static List<String> splitAscii(String text) throws IOException {
        if (text.isEmpty() || !text.equals(text.trim()) || text.matches(".*\\s{2,}.*")) throw new IOException("text whitespace drift");
        List<String> output = new ArrayList<>();
        for (int i=0;i<text.length();) {
            char c=text.charAt(i);
            if (Character.isWhitespace(c)) { i++; continue; }
            if (isWord(c)) {
                int start=i++; while(i<text.length() && isWord(text.charAt(i))) i++;
                output.add(text.substring(start,i));
            } else {
                String part=String.valueOf(c); if(!PUNCTUATION.contains(part)) throw new IOException("unsupported character: "+part);
                output.add(part); i++;
            }
        }
        return output;
    }

    private static boolean isWord(char c) { return (c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='\''; }
    private static long[] toLongArray(List<Long> values) { long[] out=new long[values.size()]; for(int i=0;i<out.length;i++)out[i]=values.get(i); return out; }

    private static float[] readStyleRow(File raw, int index) throws Exception {
        byte[] data = Files.readAllBytes(raw.toPath());
        ByteBuffer buffer = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN);
        buffer.position(index * 256 * Float.BYTES);
        float[] result = new float[256]; for(int i=0;i<result.length;i++)result[i]=buffer.getFloat();
        return result;
    }
}

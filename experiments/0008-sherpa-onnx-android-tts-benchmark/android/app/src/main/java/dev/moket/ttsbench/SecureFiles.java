package dev.moket.ttsbench;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.util.*;

public final class SecureFiles {
    private SecureFiles() {}
    public static Map<String,File> verify(File externalRoot, Map<String,String> inventory) throws IOException {
        Path root = externalRoot.toPath().toRealPath(LinkOption.NOFOLLOW_LINKS);
        Map<String,File> result = new LinkedHashMap<>();
        for (var e : inventory.entrySet()) {
            Path relative;
            try { relative = Paths.get(e.getKey()); } catch (InvalidPathException x) { throw new IOException("invalid path", x); }
            if (relative.isAbsolute() || relative.normalize().startsWith("..")) throw new IOException("path escapes external files root: "+e.getKey());
            Path cursor=root;
            for(Path part:relative) { cursor=cursor.resolve(part); if(Files.isSymbolicLink(cursor)) throw new IOException("symlink forbidden: "+e.getKey()); }
            Path file=root.resolve(relative).normalize();
            // Android's emulated external-storage provider can report false from
            // regular-file stat calls for files staged through ADB. Symlinks were
            // rejected component by component above; opening and hashing below is
            // the authoritative existence/readability check.
            if(!file.startsWith(root)) throw new IOException("path escapes external files root: "+e.getKey());
            // toRealPath() is denied by Android's scoped-storage FUSE layer even
            // for app-owned external files. Normalization plus the per-component
            // symlink rejection above provides the canonical containment check.
            Path real=file;
            String actual=sha256(real.toFile());
            if(!MessageDigest.isEqual(actual.getBytes(java.nio.charset.StandardCharsets.US_ASCII), e.getValue().getBytes(java.nio.charset.StandardCharsets.US_ASCII))) throw new IOException("hash mismatch: "+e.getKey());
            result.put(e.getKey(), real.toFile());
        }
        return Collections.unmodifiableMap(result);
    }
    public static String sha256(File file) throws IOException {
        try { MessageDigest d=MessageDigest.getInstance("SHA-256"); try(InputStream in=new BufferedInputStream(new FileInputStream(file))){byte[] b=new byte[65536];for(int n;(n=in.read(b))>=0;)if(n>0)d.update(b,0,n);} StringBuilder hex=new StringBuilder(64);for(byte value:d.digest())hex.append(String.format(Locale.ROOT,"%02x",value&0xff));return hex.toString(); }
        catch(NoSuchAlgorithmException impossible){throw new AssertionError(impossible);}
    }
}

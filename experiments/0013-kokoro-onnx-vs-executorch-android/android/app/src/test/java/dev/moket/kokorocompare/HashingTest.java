package dev.moket.kokorocompare;

import static org.junit.Assert.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import org.junit.Test;

public final class HashingTest {
    @Test public void acceptsPinnedRegularFileInsideCanonicalRoot() throws Exception {
        Path root=Files.createTempDirectory("hash-root");
        try { Path file=root.resolve("model.onnx");Files.write(file,"test".getBytes(StandardCharsets.US_ASCII));Hashing.verifyRegularPinnedFile(root.toFile(),"model.onnx",4,"9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"); }
        finally { delete(root); }
    }
    @Test public void rejectsCanonicalEscapeEvenThroughSymlink() throws Exception {
        Path root=Files.createTempDirectory("hash-root"),outside=Files.createTempFile("outside",".bin");
        try { Files.write(outside,"test".getBytes(StandardCharsets.US_ASCII));Files.createSymbolicLink(root.resolve("model.onnx"),outside);try{Hashing.verifyRegularPinnedFile(root.toFile(),"model.onnx",4,"9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08");fail("escape accepted");}catch(IOException expected){assertTrue(expected.getMessage().contains("unsafe"));} }
        finally { delete(root);Files.deleteIfExists(outside); }
    }
    @Test public void rejectsWrongHash() throws Exception {
        Path root=Files.createTempDirectory("hash-root");
        try { Files.write(root.resolve("model.onnx"),"test".getBytes(StandardCharsets.US_ASCII));try{Hashing.verifyRegularPinnedFile(root.toFile(),"model.onnx",4,"0000000000000000000000000000000000000000000000000000000000000000");fail("wrong hash accepted");}catch(IOException expected){assertTrue(expected.getMessage().contains("SHA-256"));} }
        finally { delete(root); }
    }
    private static void delete(Path path)throws IOException{if(!Files.exists(path))return;try(var entries=Files.list(path)){for(Path entry:entries.toList())Files.deleteIfExists(entry);}Files.deleteIfExists(path);}
}

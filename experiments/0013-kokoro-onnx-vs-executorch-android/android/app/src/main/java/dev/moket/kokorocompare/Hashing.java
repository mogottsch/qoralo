package dev.moket.kokorocompare;

import java.io.*;
import java.nio.*;
import java.nio.file.Files;
import java.security.MessageDigest;

final class Hashing {
    private Hashing() {}

    static String fileSha256(File file) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream input = new BufferedInputStream(new FileInputStream(file))) {
            byte[] buffer = new byte[1024 * 1024];
            for (int count; (count = input.read(buffer)) >= 0; ) {
                if (count > 0) digest.update(buffer, 0, count);
            }
        }
        return hex(digest.digest());
    }

    static String littleEndianLongSha256(long[] values) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        ByteBuffer buffer = ByteBuffer.allocate(values.length * Long.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        for (long value : values) buffer.putLong(value);
        digest.update(buffer.array());
        return hex(digest.digest());
    }

    static byte[] littleEndianFloats(float[] values) {
        ByteBuffer buffer = ByteBuffer.allocate(values.length * Float.BYTES).order(ByteOrder.LITTLE_ENDIAN);
        for (float value : values) buffer.putFloat(value);
        return buffer.array();
    }

    static String littleEndianFloatSha256(float[] values) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        digest.update(littleEndianFloats(values));
        return hex(digest.digest());
    }

    static void verifyRegularPinnedFile(File root, String relative, long bytes, String sha256) throws Exception {
        File file = new File(root, relative);
        String rootPath = root.getCanonicalPath() + File.separator;
        String filePath = file.getCanonicalPath();
        // Android's emulated external-storage/FUSE layer can report the whole
        // app-scoped path as symbolic. Canonical containment plus regular-file,
        // exact-size, and exact-hash checks remains fail-closed without relying
        // on that unreliable flag.
        if (!filePath.startsWith(rootPath) || !file.isFile()) {
            throw new IOException("unsafe or missing file: " + relative + " root=" + rootPath + " file=" + filePath + " regular=" + file.isFile());
        }
        if (file.length() != bytes) throw new IOException("size mismatch: " + relative);
        String actual = fileSha256(file);
        if (!actual.equals(sha256)) throw new IOException("SHA-256 mismatch: " + relative);
    }

    private static String hex(byte[] bytes) {
        StringBuilder output = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) output.append(String.format("%02x", value & 0xff));
        return output.toString();
    }
}

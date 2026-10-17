package dev.qoralo.podcast.e2e

import android.app.Application
import android.content.ContentProvider
import android.content.ContentValues
import android.database.Cursor
import android.database.MatrixCursor
import android.net.Uri
import android.provider.OpenableColumns
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowContentResolver

@RunWith(RobolectricTestRunner::class)
@Config(application = Application::class)
class ShortProductExportCursorTest {
    private val uri = Uri.parse("content://com.android.providers.downloads.documents/document/owned")
    private val expected = "podcast-owned.wav"
    private val columns = arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE)
    private val provider = object : ContentProvider() {
        var result: Cursor? = null
        override fun onCreate() = true
        override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor? {
            assertEquals(this@ShortProductExportCursorTest.uri, uri)
            assertArrayEquals(columns, projection)
            assertNull(selection); assertNull(selectionArgs); assertNull(sortOrder)
            return result
        }
        override fun getType(uri: Uri): String? = null
        override fun insert(uri: Uri, values: ContentValues?): Uri? = error("No document writes allowed")
        override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?) = error("No document writes allowed")
        override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?) = error("No document writes allowed")
    }

    private open inner class TrackedCursor : MatrixCursor(columns) {
        var closes = 0
        override fun close() { closes++; super.close() }
    }

    @Before fun registerProvider() {
        ShadowContentResolver.registerProviderInternal(uri.authority, provider)
    }

    private fun inspect(cursor: Cursor?) {
        provider.result = cursor
        ShortProductDiagnostics.requireEmptyOwnedExportDocument(
            ApplicationProvider.getApplicationContext<Application>().contentResolver, uri, expected,
        )
    }

    private fun rejected(cursor: TrackedCursor) {
        try {
            assertThrows(IllegalArgumentException::class.java) { inspect(cursor) }
        } finally {
            assertTrue(cursor.isClosed)
            assertEquals(1, cursor.closes)
        }
    }

    @Test fun validEmptyNamedDocumentClosesBeforeReturning() {
        val cursor = TrackedCursor().apply { addRow(arrayOf<Any?>(expected, 0L)) }
        inspect(cursor)
        assertTrue(cursor.isClosed)
        assertEquals(1, cursor.closes)
    }

    @Test fun missingCursorIsRejected() {
        assertThrows(IllegalArgumentException::class.java) { inspect(null) }
    }

    @Test fun emptyCursorIsRejectedAndClosed() = rejected(TrackedCursor())

    @Test fun wrongNameIsRejectedAndClosed() = rejected(TrackedCursor().apply { addRow(arrayOf<Any?>("other.wav", 0L)) })

    @Test fun unknownSizeIsRejectedAndClosed() = rejected(TrackedCursor().apply { addRow(arrayOf<Any?>(expected, null)) })

    @Test fun nonemptyDocumentIsRejectedAndClosed() = rejected(TrackedCursor().apply { addRow(arrayOf<Any?>(expected, 1L)) })

    @Test fun negativeSizeIsRejectedAndClosed() = rejected(TrackedCursor().apply { addRow(arrayOf<Any?>(expected, -1L)) })

    @Test fun metadataReadExceptionIsPropagatedAndCursorClosed() {
        val failure = IllegalStateException("Injected metadata read failure")
        val cursor = object : TrackedCursor() {
            override fun getLong(column: Int): Long = throw failure
        }.apply { addRow(arrayOf<Any?>(expected, 0L)) }
        val observed = assertThrows(IllegalStateException::class.java) { inspect(cursor) }
        assertSame(failure, observed)
        assertTrue(cursor.isClosed)
        assertEquals(1, cursor.closes)
    }
}

package dev.vibevoice.podcast.e2e

import org.junit.Assert.*
import org.junit.Test
import org.junit.Rule
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import android.graphics.Bitmap

@RunWith(RobolectricTestRunner::class)
class OwnedWindowCapturePolicyTest {
    @get:Rule val temp=TemporaryFolder()
    private val app="dev.vibevoice.podcast.internal"
    private val owned="mCurrentFocus=Window{123 u0 $app/dev.vibevoice.podcast.MainActivity}"
    @Test fun windowsOnlyDumpWithoutFocusSkipsInsteadOfThrowing() {
        assertNull(OwnedWindowCapturePolicy.ownedFocus("WINDOW MANAGER WINDOWS\n  Window #0 Window{123 u0 $app/MainActivity}",app))
    }
    @Test fun missingFocusSkipsBitmapAndAllowsFunctionalChecksToContinue() {
        var screenshots=0
        val result=OwnedWindowCapturePolicy.capture(app,temp.newFolder(),"missing",{"No focus field"},{screenshots++;null})
        assertEquals(0,screenshots);assertEquals("skipped_unknown_window_owner",result.getString("status"))
        assertTrue(result.getBoolean("functionalTestContinues"))
    }
    @Test fun changedFocusNeverClaimsPairedOwnedScreenshot() {
        var reads=0
        val result=OwnedWindowCapturePolicy.capture(app,temp.newFolder(),"changed",{if(reads++==0) owned else "mCurrentFocus=Window{other/package}"},
            {Bitmap.createBitmap(1,1,Bitmap.Config.ARGB_8888)})
        assertEquals("unpaired_window_changed",result.getString("status"));assertFalse(result.getBoolean("capturePaired"))
        assertTrue(result.getBoolean("functionalTestContinues"))
    }
    @Test fun captureTransportFailureIsNonFatalAndDoesNotExposeRawMessage() {
        val result=OwnedWindowCapturePolicy.capture(app,temp.newFolder(),"failed",{error("private capture exception")},{null})
        assertEquals("capture_unavailable",result.getString("status"));assertTrue(result.getBoolean("functionalTestContinues"))
        assertFalse(result.toString().contains("private capture exception"))
    }
    @Test fun fullDumpWithUniqueOwnedFocusCanBePaired() {
        assertEquals(owned,OwnedWindowCapturePolicy.ownedFocus("WINDOW MANAGER\n  $owned\nOther state",app))
        assertEquals(owned,OwnedWindowCapturePolicy.ownedFocus("$owned\n$owned",app))
    }
    @Test fun foreignNullOrAmbiguousFocusIsNotCapturedAsOwned() {
        for(dump in listOf("mCurrentFocus=null","mCurrentFocus=Window{other/package}","$owned\nmCurrentFocus=Window{other/package}"))
            assertNull(OwnedWindowCapturePolicy.ownedFocus(dump,app))
    }
}

package dev.qoralo.podcast.e2e

import android.graphics.Bitmap
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/** Optional visual evidence never turns an unavailable dump field into a functional/model failure. */
internal object OwnedWindowCapturePolicy {
    fun ownedFocus(dump:String,packageName:String):String? {
        val focus=dump.lineSequence().map(String::trim).filter {it.startsWith("mCurrentFocus=")}.distinct().singleOrNull() ?: return null
        return focus.takeIf {it.contains("$packageName/")}
    }
    fun capture(packageName:String,root:File,name:String,readWindowDump:()->String,takeScreenshot:()->Bitmap?):JSONObject {
        return try {
            require(Regex("[A-Za-z0-9-]{1,80}").matches(name))
            fun owner(side:String):String? {
                val dump=readWindowDump();require(dump.length<=1_048_576)
                val file=File(root,"private-$name-window-$side.txt");require(!file.exists());file.writeText(dump)
                return ownedFocus(dump,packageName)
            }
            val before=owner("before")
            if(before==null) JSONObject().put("status","skipped_unknown_window_owner").put("capturePaired",false)
            else {
                val image=File(root,"private-$name.png");require(!image.exists())
                val bitmap=requireNotNull(takeScreenshot())
                try {image.outputStream().use {require(bitmap.compress(Bitmap.CompressFormat.PNG,100,it))}} finally {bitmap.recycle()}
                val after=owner("after")
                val hash=MessageDigest.getInstance("SHA-256");image.inputStream().use {input -> val buffer=ByteArray(65536);while(true){val count=input.read(buffer);if(count<0)break;hash.update(buffer,0,count)}}
                JSONObject().put("status",if(before==after) "paired" else "unpaired_window_changed").put("capturePaired",before==after)
                    .put("windowOwnerBefore",before).put("windowOwnerAfter",after).put("imageBytes",image.length())
                    .put("imageSha256",hash.digest().joinToString(""){"%02x".format(it)})
            }
        } catch(error:Throwable) {
            JSONObject().put("status","capture_unavailable").put("errorType",error.javaClass.simpleName).put("capturePaired",false)
        }.put("functionalTestContinues",true)
    }
}

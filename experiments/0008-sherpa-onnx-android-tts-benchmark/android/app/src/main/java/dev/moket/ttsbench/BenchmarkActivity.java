package dev.moket.ttsbench;

import android.app.Activity;
import android.os.Bundle;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;

/** Headless entry point. Launch with descriptor and campaign extras; it never plays audio. */
public final class BenchmarkActivity extends Activity {
    @Override public void onCreate(Bundle state){super.onCreate(state);new Thread(this::execute,"benchmark").start();}
    private void execute(){
        File external=getExternalFilesDir(null);String descriptorName=getIntent().getStringExtra("descriptor");String campaign=getIntent().getStringExtra("campaign_id");
        if(descriptorName==null||campaign==null||!campaign.matches("[A-Za-z0-9._-]+")){finishAndRemoveTask();return;}
        try{
            File descriptor=SecureFiles.verify(external,Map.of(descriptorName,getIntent().getStringExtra("descriptor_sha256"))).get(descriptorName);
            BenchmarkDescriptor d=BenchmarkDescriptor.parse(new String(Files.readAllBytes(descriptor.toPath()),StandardCharsets.UTF_8));Map<String,File> verified=SecureFiles.verify(external,d.files());
            File transcript=verified.get(d.transcript());if(transcript==null||!SecureFiles.sha256(transcript).equals(d.transcriptSha256()))throw new IOException("transcript pin mismatch");
            BenchmarkRunner runner=new BenchmarkRunner(System::nanoTime,SherpaOfflineTtsEngine::create,new AndroidMemoryReader());
            File output=new File(external,"results/"+campaign);BenchmarkResult result=runner.run(d,verified,output,campaign);
            BenchmarkRunner.writeResultNew(new File(output,campaign+".json"),result);
        }catch(Exception e){try{BenchmarkResult failure=new BenchmarkResult(0,List.of(),null,new BenchmarkResult.Failure("bootstrap","failure",String.valueOf(e.getMessage()),e.getClass().getName()));BenchmarkRunner.writeResultNew(new File(external,"results/"+campaign+"/"+campaign+".json"),failure);}catch(Exception ignored){}}
        finally{runOnUiThread(this::finishAndRemoveTask);}
    }
}

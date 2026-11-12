package app.flowdrop.mobile;
import android.app.job.*;
public final class UpdateJobService extends JobService {
  private Thread worker;
  @Override public boolean onStartJob(JobParameters params){worker=new Thread(()->{boolean ok=AppUpdates.check(getApplicationContext());jobFinished(params,!ok);},"flowdrop-update-job");worker.start();return true;}
  @Override public boolean onStopJob(JobParameters params){if(worker!=null)worker.interrupt();return true;}
}

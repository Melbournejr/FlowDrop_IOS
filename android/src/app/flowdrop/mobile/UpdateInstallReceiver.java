package app.flowdrop.mobile;
import android.content.*;
import android.content.pm.PackageInstaller;
public final class UpdateInstallReceiver extends BroadcastReceiver {
  @Override public void onReceive(Context context,Intent intent){AppUpdates.installResult(context,intent.getIntExtra(PackageInstaller.EXTRA_STATUS,PackageInstaller.STATUS_FAILURE),intent.getParcelableExtra(Intent.EXTRA_INTENT),intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE));}
}

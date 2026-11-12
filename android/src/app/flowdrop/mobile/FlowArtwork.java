package app.flowdrop.mobile;

import android.content.Context;
import android.graphics.*;
import android.view.View;

/** Small vector illustration drawn by Android Canvas; no bitmap or renderer dependency. */
public final class FlowArtwork extends View {
  private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
  private final RectF rect=new RectF();
  public FlowArtwork(Context context){super(context);setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);}
  private void line(Canvas canvas,float x1,float y1,float x2,float y2,int color,float width){paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(width);paint.setColor(color);paint.setStrokeCap(Paint.Cap.ROUND);canvas.drawLine(x1,y1,x2,y2,paint);}
  private void box(Canvas canvas,float left,float top,float right,float bottom,float radius,int color,boolean fill){paint.setStyle(fill?Paint.Style.FILL:Paint.Style.STROKE);paint.setColor(color);paint.setStrokeWidth(1.5f);rect.set(left,top,right,bottom);canvas.drawRoundRect(rect,radius,radius,paint);}
  @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);canvas.save();float scale=Math.min(getWidth()/320f,getHeight()/142f);canvas.translate((getWidth()-320*scale)/2,(getHeight()-142*scale)/2);canvas.scale(scale,scale);
    paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(1);paint.setColor(0xff25453f);rect.set(42,12,279,132);canvas.drawOval(rect,paint);rect.set(70,32,250,112);canvas.drawOval(rect,paint);
    box(canvas,55,40,136,101,12,0xff172c3b,true);box(canvas,55,40,136,101,12,0xff436778,false);box(canvas,64,48,127,88,5,0xff203e48,true);line(canvas,47,104,145,104,0xff9bb8c3,3);line(canvas,87,108,105,108,0xff9bb8c3,2);
    box(canvas,208,25,254,111,12,0xff1c3b32,true);box(canvas,208,25,254,111,12,0xff58e6a3,false);line(canvas,223,33,239,33,0xff58e6a3,2);line(canvas,225,102,237,102,0xff58e6a3,2);
    paint.setStyle(Paint.Style.FILL);paint.setColor(0xff58e6a3);canvas.drawCircle(171,67,23,paint);line(canvas,157,61,183,61,0xff0b2b20,2.5f);line(canvas,178,56,183,61,0xff0b2b20,2.5f);line(canvas,178,66,183,61,0xff0b2b20,2.5f);line(canvas,183,74,157,74,0xff0b2b20,2.5f);line(canvas,162,69,157,74,0xff0b2b20,2.5f);line(canvas,162,79,157,74,0xff0b2b20,2.5f);
    paint.setColor(0xff58e6a3);canvas.drawCircle(77,23,3,paint);paint.setColor(0xff9fc5ff);canvas.drawCircle(280,93,3,paint);canvas.restore();
  }
}

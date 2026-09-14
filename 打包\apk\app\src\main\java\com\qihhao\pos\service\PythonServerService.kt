package com.qihhao.pos.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.qihhao.pos.Bridge
import com.qihhao.pos.MainActivity
import com.qihhao.pos.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import timber.log.Timber

/**
 * Python 后台服务 — 保持 Python 后端在 Activity 切换时持续运行
 *
 * 使用 START_STICKY + startForeground 确保 Android 不会回收服务，
 * 并用通知栏图标提示用户收银服务正在运行。
 */
class PythonServerService : Service() {

    companion object {
        private const val TAG = "PyServerSvc"
        private const val CHANNEL_ID = "qihhao_pos_core"
        private const val NOTIFY_ID = 1001
        private const val EXTRA_PORT_CANDIDATES = "port_candidates"
        const val ACTION_STOP = "com.qihhao.pos.action.STOP_SERVICE"

        /**
         * 启动服务（传入候选端口）
         */
        fun start(context: Context, candidates: List<Int> = (8000..8010).toList()) {
            val intent = Intent(context, PythonServerService::class.java).apply {
                putExtra(EXTRA_PORT_CANDIDATES, IntArray(candidates.size) { candidates[it] })
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        /**
         * 停止服务
         */
        fun stop(context: Context) {
            context.stopService(Intent(context, PythonServerService::class.java))
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        Timber.tag(TAG).i("onCreate")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Timber.tag(TAG).i("onStartCommand action=${intent?.action}")

        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }

        try {
            startForeground(NOTIFY_ID, createNotification())

            val portArray = intent?.getIntArrayExtra(EXTRA_PORT_CANDIDATES)
            val ports = portArray?.toList() ?: (8000..8010).toList()

            scope.launch {
                val port = withContext(Dispatchers.IO) {
                    Bridge.startServer(this@PythonServerService, ports)
                }
                if (port > 0) {
                    Timber.tag(TAG).i("Service Python running on port $port")
                } else {
                    Timber.tag(TAG).e("Service Python start failed")
                    stopSelf()
                }
            }
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Service start error")
            stopSelf()
        }

        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        Timber.tag(TAG).i("onDestroy")
        Bridge.stopServer()
        scope.cancel()
    }

    // ================================================================

    private fun createNotification(): Notification {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(NotificationManager::class.java)
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notify_channel_name),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.notify_channel_desc)
                setShowBadge(false)
                enableLights(false)
                enableVibration(false)
            }
            mgr.createNotificationChannel(channel)
        }

        val contentIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(getString(R.string.notify_service_running))
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(contentIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .build()
    }
}

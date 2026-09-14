package com.qihhao.pos

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.File

/**
 * 柒号收银系统 主界面
 *
 * 核心职责：
 * 1. 在后台线程启动 Python 后端 (FastAPI + uvicorn)
 * 2. 全屏 WebView 加载 localhost:{port}/ 渲染收银前端
 * 3. 处理 USB 设备插入事件，Bridge 层对接硬件
 * 4. 提供 JavaScript -> Kotlin -> Python 三层桥接
 *
 * @author QihhaoDev
 */
class MainActivity : AppCompatActivity() {

    companion object {
        private const val TAG = "QihhaoMain"
        const val USB_PERMISSION_ACCESS = "com.qihhao.pos.USB_PERMISSION"
    }

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var errorText: TextView

    private var serverPort: Int = 0
    private var pythonReady = false

    // USB Manager
    private lateinit var usbManager: UsbManager

    // USB 广播接收器
    private val usbActionReceiver = object : UsbReceiver() {
        override fun onUsbDeviceAttached(device: UsbDevice) {
            handleUsbAttached(device)
        }

        override fun onUsbDeviceDetached(device: UsbDevice) {
            Bridge.releaseUsbDevice(device.deviceId)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Timber.tag(TAG).d("MainActivity onCreate")

        // 防截屏
        window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
        )

        setContentView(R.layout.activity_main)

        initViews()
        hideSystemUI()

        usbManager = getSystemService(Context.USB_SERVICE) as UsbManager
        registerUsbReceiver()

        // 返回键由 WebView 消费
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (::webView.isInitialized && webView.canGoBack()) {
                    webView.goBack()
                }
            }
        })

        startPythonAndLoad()

        // 处理外部 USB 启动
        handleIntent(intent)
    }

    private fun initViews() {
        webView = findViewById(R.id.webView)
        progressBar = findViewById(R.id.progressBar)
        errorText = findViewById(R.id.errorText)
        configureWebView()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            setSupportMultipleWindows(false)

            setSupportZoom(false)
            builtInZoomControls = false
            displayZoomControls = false

            cacheMode = WebSettings.LOAD_DEFAULT
            useWideViewPort = true
            loadWithOverviewMode = true

            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            mediaPlaybackRequiresUserGesture = false
            javaScriptCanOpenWindowsAutomatically = true
            userAgentString = "$userAgentString QihhaoPOS/3.2.0 (Android)"
        }

        webView.addJavascriptInterface(BackgroundBridge(this), "AndroidBridge")

        webView.webChromeClient = object : WebChromeClient() {
            override fun onConsoleMessage(msg: ConsoleMessage): Boolean {
                val log = "${msg.message()} [line ${msg.lineNumber()}]"
                when (msg.messageLevel()) {
                    ConsoleMessage.MessageLevel.ERROR -> Timber.tag("WebViewJS").e(log)
                    ConsoleMessage.MessageLevel.WARNING -> Timber.tag("WebViewJS").w(log)
                    else -> Timber.tag("WebViewJS").d(log)
                }
                return true
            }
            override fun onPermissionRequest(request: PermissionRequest) {
                runOnUiThread { request.grant(request.resources) }
            }
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                progressBar.visibility = View.GONE
                Timber.tag(TAG).v("Page loaded: $url")
            }

            override fun onReceivedError(
                view: WebView?,
                errorCode: Int,
                description: String?,
                failingUrl: String?
            ) {
                Timber.tag(TAG).e("WebView error: $errorCode $description $failingUrl")
                if (!pythonReady) {
                    // 等待服务就绪
                } else {
                    showError("加载失败: $description")
                }
            }

            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?
            ): Boolean {
                val url = request?.url ?: return false
                if (url.host == "localhost" || url.host == "127.0.0.1" || url.scheme == "file") {
                    return false
                }
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url.toString())))
                } catch (e: Exception) {
                    Timber.tag(TAG).w("No browser for $url")
                }
                return true
            }
        }
    }

    /**
     * 启动 Python 后端 → WebView 加载
     */
    private fun startPythonAndLoad() {
        showProgress("正在启动收银系统…")

        lifecycleScope.launch {
            try {
                withContext(Dispatchers.IO) {
                    val ports = (8000..8010).toList()
                    serverPort = Bridge.startServer(this@MainActivity, ports)
                }

                if (serverPort <= 0) {
                    showError("服务启动失败，请检查安装包完整性")
                    return@launch
                }

                pythonReady = true
                Timber.tag(TAG).i("Python server on port $serverPort")
                delay(3000)

                withContext(Dispatchers.Main) {
                    val url = "http://localhost:$serverPort/"
                    Timber.tag(TAG).i("Loading WebView: $url")
                    webView.loadUrl(url)
                }
            } catch (e: Exception) {
                Timber.tag(TAG).e(e, "Server start failed")
                showError("启动异常: ${e.message}")
            }
        }
    }

    /**
     * USB 广播注册
     */
    private fun registerUsbReceiver() {
        val filter = IntentFilter().apply {
            addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED)
            addAction(UsbManager.ACTION_USB_DEVICE_DETACHED)
            addAction(USB_PERMISSION_ACCESS)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(usbActionReceiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            registerReceiver(usbActionReceiver, filter)
        }
    }

    private fun handleUsbAttached(device: UsbDevice) {
        Timber.tag(TAG).i("USB attached: vid=${device.vendorId} pid=${device.productId} class=${device.deviceClass}")
        if (usbManager.hasPermission(device)) {
            Bridge.attachUsb(this, device)
        } else {
            requestUsbPermission(device)
        }
    }

    private fun requestUsbPermission(device: UsbDevice) {
        val intent = Intent(USB_PERMISSION_ACCESS).apply { setPackage(packageName) }
        val pi = PendingIntent.getBroadcast(
            this, device.deviceId, intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        usbManager.requestPermission(device, pi)
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        intent ?: return
        if (intent.action == UsbManager.ACTION_USB_DEVICE_ATTACHED) {
            val device = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getParcelableExtra(UsbManager.EXTRA_DEVICE)
            }
            device?.let { handleUsbAttached(it) }
        }
    }

    override fun onResume() {
        super.onResume()
        hideSystemUI()
        if (::webView.isInitialized) webView.onResume()
    }

    override fun onPause() {
        super.onPause()
        if (::webView.isInitialized) webView.onPause()
    }

    override fun onDestroy() {
        super.onDestroy()
        try { unregisterReceiver(usbActionReceiver) } catch (_: Exception) {}
        Bridge.stopServer()
    }

    /**
     * 沉浸式全屏 — 隐藏状态栏和导航栏
     */
    private fun hideSystemUI() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.insetsController?.let {
                it.hide(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
                it.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_FULLSCREEN
            )
        }
    }

    private fun showProgress(msg: String) {
        runOnUiThread {
            progressBar.visibility = View.VISIBLE
            errorText.visibility = View.GONE
        }
    }

    private fun showError(msg: String) {
        runOnUiThread {
            progressBar.visibility = View.GONE
            errorText.visibility = View.VISIBLE
            errorText.text = msg
        }
    }

    /**
     * JS 桥接
     */
    inner class BackgroundBridge(private val context: Context) {

        @JavascriptInterface
        fun getVersion(): String = "3.2.0"

        @JavascriptInterface
        fun getServerPort(): Int = serverPort

        @JavascriptInterface
        fun scanUsbDevices(): String = Bridge.scanUsbDevices(context)

        @JavascriptInterface
        fun attachUsb(vid: Int, pid: Int): String = Bridge.attachUsb(context, vid, pid)

        @JavascriptInterface
        fun scanBluetoothDevices(): String = Bridge.scanBluetoothDevices(context)

        @JavascriptInterface
        fun attachBluetooth(mac: String): String = Bridge.attachBluetooth(context, mac)

        @JavascriptInterface
        fun releaseFd(fd: Int): Boolean = Bridge.releaseFd(fd)

        @JavascriptInterface
        fun log(message: String) {
            Timber.tag("JS_LOG").d(message)
        }

        @JavascriptInterface
        fun exportLogs(): String {
            return try {
                val logFile = File(context.filesDir, "logs/app.log")
                Uri.fromFile(logFile).toString()
            } catch (e: Exception) {
                """{"error": "${e.message}"}"""
            }
        }
    }
}

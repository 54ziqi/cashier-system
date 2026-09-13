package com.qihhao.pos

import android.content.Context
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.ParcelFileDescriptor
import android.os.Build
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.google.gson.Gson
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import timber.log.Timber
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import kotlin.concurrent.Volatile

/**
 * Python 桥接层 (Singleton)
 *
 * 职责：
 * 1. 初始化 Chaquopy 运行时、注入全局配置（数据目录、主端口、PID/VID 等）
 * 2. startServer() 在 Python 子线程启动 uvicorn
 * 3. stopServer() 优雅关闭
 * 4. scanUsbDevices() / attachUsb() 使用 UsbManager + usb-serial-for-android
 * 5. scanBluetoothDevices() / attachBluetooth() 使用 BluetoothAdapter + RFCOMM
 * 6. releaseFd() 关闭 ParcelFileDescriptor
 *
 * 所有方法均返回 JSON 字符串，便于 WebView JS 消费。
 */
object Bridge {

    private const val TAG = "QihhaoBridge"
    private const val MODULE_NAME = "run"
    private const val PYTHON_ENTRY = "serve"

    private val gson = Gson()

    // Chaquopy 引用
    @Volatile
    private var python: Python? = null

    @Volatile
    private var serverModule: PyObject? = null

    @Volatile
    private var serverThread: Thread? = null

    // 已打开的设备描述符
    private val openDescriptors = mutableMapOf<Int, ParcelFileDescriptor>()

    // 已打开的 USB 串口设备
    @Volatile
    private var currentUsbConnection: Any? = null

    // 蓝牙套接字
    @Volatile
    private var bluetoothSocket: java.net.Socket? = null

    // 数据目录
    @Volatile
    private var dataDir: String = ""

    /**
     * 启动 Python 服务
     *
     * @param context 应用 Context
     * @param portCandidates 候选端口列表
     * @return 实际使用端口号，-1 表示失败
     */
    fun startServer(context: Context, portCandidates: List<Int>): Int {
        val startNs = System.nanoTime()
        Timber.tag(TAG).i("startServer begin, ports=$portCandidates")

        try {
            initPython(context)

            val module = getServerModule()
            if (module == null) {
                Timber.tag(TAG).e("Python run.py module is null")
                return -1
            }

            // 用 Python 层 find_free_port 确定端口（与 cmd_serve 逻辑一致）
            var selectedPort = -1
            for (p in portCandidates) {
                try {
                    val callAttr = module.callAttr("find_free_port", "127.0.0.1", p)
                    val port = callAttr.toInt()
                    if (port > 0) {
                        selectedPort = port
                        Timber.tag(TAG).d("Port $port is free")
                        break
                    }
                } catch (_: Exception) {
                    Timber.tag(TAG).d("Port $p not free, try next")
                }
            }

            if (selectedPort <= 0) {
                Timber.tag(TAG).e("No available port in $portCandidates")
                return -1
            }

            // 注入配置（Chaquopy 环境下）
            injectConfig(context, selectedPort)

            // 启动 uvicorn
            Timber.tag(TAG).i("Starting uvicorn on port $selectedPort")
            serverThread = Thread {
                try {
                    module.callAttr(PYTHON_ENTRY, selectedPort)
                } catch (e: Exception) {
                    Timber.tag(TAG).e(e, "Python server thread crashed")
                }
            }, "PyUvicorn").apply {
                isDaemon = false
                start()
            }

            // 等待 Python 进程就绪
            Thread.sleep(500)

            val elapsed = (System.nanoTime() - startNs) / 1_000_000
            Timber.tag(TAG).i("startServer done, port=$selectedPort, time=${elapsed}ms")
            return selectedPort

        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "startServer failed")
            return -1
        }
    }

    /**
     * 停止 Python 服务
     */
    fun stopServer() {
        Timber.tag(TAG).i("stopServer")
        try {
            serverModule?.callAttr("shutdown")
        } catch (e: Exception) {
            Timber.tag(TAG).w(e, "shutdown module fail")
        }
        releaseAll()
    }

    // ========== USB ==========

    /**
     * 扫描已连接的 USB 串口设备
     */
    fun scanUsbDevices(context: Context): String {
        val result = JsonObject()
        try {
            val usbManager = context.getSystemService(Context.USB_SERVICE) as UsbManager
            val devices = usbManager.deviceList

            val arr = JsonArray()
            for ((name, dev) in devices) {
                val item = JsonObject().apply {
                    addProperty("name", name)
                    addProperty("vid", String.format("0x%04X", dev.vendorId))
                    addProperty("pid", String.format("0x%04X", dev.productId))
                    addProperty("class", dev.deviceClass)
                    addProperty("deviceId", dev.deviceId)
                    addProperty("hasPermission", usbManager.hasPermission(dev))
                }
                arr.add(item)
            }
            result.add("devices", arr)
            result.addProperty("ok", true)
            Timber.tag(TAG).d("scanUsbDevices: ${devices.size} devices")
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "scanUsbDevices error")
            result.addProperty("ok", false)
            result.addProperty("error", e.message ?: "unknown")
        }
        return result.toString()
    }

    /**
     * 通过 VID/PID 打开 USB 串口设备
     *
     * 将 ParcelFileDescriptor 的 fd 传给 Python 层
     */
    fun attachUsb(context: Context, vid: Int, pid: Int): String {
        val result = JsonObject()
        try {
            val usbManager = context.getSystemService(Context.USB_SERVICE) as UsbManager
            val device = usbManager.deviceList.values.firstOrNull {
                it.vendorId == vid && it.productId == pid
            }

            if (device == null) {
                result.addProperty("ok", false)
                result.addProperty("error", "USB device not found: vid=0x${"%04X".format(vid)} pid=0x${"%04X".format(pid)}")
                return result.toString()
            }

            // 检查权限
            if (!usbManager.hasPermission(device)) {
                result.addProperty("ok", false)
                result.addProperty("error", "no_permission")
                return result.toString()
            }

            val connection = usbManager.openDevice(device)
            if (connection == null) {
                result.addProperty("ok", false)
                result.addProperty("error", "open failed")
                return result.toString()
            }

            // 获取 fd（通过反射从 UsbDeviceConnection）
            val pfd = connection.fileDescriptor
            if (pfd == null || !pfd.valid()) {
                result.addProperty("ok", false)
                result.addProperty("error", "invalid fd")
                connection.close()
                return result.toString()
            }

            // dup fd 用于传递
            val dupFd = ParcelFileDescriptor.dup(pfd)

            synchronized(openDescriptors) {
                openDescriptors[dupFd.fd] = dupFd
            }

            result.addProperty("ok", true)
            result.addProperty("fd", dupFd.fd)
            result.addProperty("deviceName", device.deviceName)
            result.addProperty("vid", vid)
            result.addProperty("pid", pid)
            result.addProperty("interfaceCount", device.interfaceCount)

            currentUsbConnection = connection
            Timber.tag(TAG).i("USB attached: fd=${dupFd.fd} vid=${"0x%04X".format(vid)} pid=${"0x%04X".format(pid)}")

        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "attachUsb error")
            result.addProperty("ok", false)
            result.addProperty("error", e.message ?: "unknown")
        }
        return result.toString()
    }

    /**
     * 通过 VID/PID 打开 USB 串口设备（UsbDevice 对象版本）
     */
    fun attachUsb(context: Context, device: UsbDevice): String {
        return attachUsb(context, device.vendorId, device.productId)
    }

    fun releaseUsbDevice(deviceId: Int) {
        Timber.tag(TAG).d("releaseUsbDevice: $deviceId")
        try {
            synchronized(openDescriptors) {
                openDescriptors[deviceId]?.close()
                openDescriptors.remove(deviceId)
            }
        } catch (_: Exception) {}
    }

    // ========== Bluetooth ==========

    /**
     * 扫描已配对蓝牙设备
     */
    fun scanBluetoothDevices(context: Context): String {
        val result = JsonObject()
        try {
            val bluetoothAdapter = android.bluetooth.BluetoothAdapter.getDefaultAdapter()
            if (bluetoothAdapter == null) {
                result.addProperty("ok", false)
                result.addProperty("error", "bluetooth not supported")
                return result.toString()
            }

            if (!bluetoothAdapter.isEnabled) {
                result.addProperty("ok", false)
                result.addProperty("error", "bluetooth disabled")
                return result.toString()
            }

            val arr = JsonArray()
            try {
                val bondedDevices = bluetoothAdapter.bondedDevices
                bondedDevices?.forEach { dev ->
                    val item = JsonObject().apply {
                        addProperty("name", dev.name ?: "Unknown")
                        addProperty("mac", dev.address)
                        addProperty("bondState", dev.bondState)
                        addProperty("type", dev.type)
                    }
                    arr.add(item)
                }
            } catch (e: SecurityException) {
                // Android 12+ 需要 BLUETOOTH_CONNECT
                result.addProperty("error", "permission denied: ${e.message}")
            }

            result.add("devices", arr)
            result.addProperty("ok", true)
            Timber.tag(TAG).d("scanBluetoothDevices: ${arr.size()} paired")

        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "scanBluetoothDevices error")
            result.addProperty("ok", false)
            result.addProperty("error", e.message ?: "unknown")
        }
        return result.toString()
    }

    /**
     * 连接蓝牙设备，创建 ParcelFileDescriptor
     *
     * 使用 SPP (RFCOMM) UUID 00001101-0000-1000-8000-00805F9B34FB
     */
    fun attachBluetooth(context: Context, mac: String): String {
        val result = JsonObject()
        try {
            val adapter = android.bluetooth.BluetoothAdapter.getDefaultAdapter()
            if (adapter == null || !adapter.isEnabled) {
                result.addProperty("ok", false)
                result.addProperty("error", "bluetooth unavailable")
                return result.toString()
            }

            val device = adapter.getRemoteDevice(mac)

            // 取消扫描以提高连接速度
            try { adapter.cancelDiscovery() } catch (_: SecurityException) {}

            val socket = device.createRfcommSocketToServiceRecord(
                java.util.UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
            )
            socket.connect()
            bluetoothSocket = socket

            val pfd = ParcelFileDescriptor.fromSocket(socket)
            synchronized(openDescriptors) {
                openDescriptors[pfd.fd] = pfd
            }

            result.addProperty("ok", true)
            result.addProperty("fd", pfd.fd)
            result.addProperty("mac", mac)
            result.addProperty("name", device.name ?: "Unknown")
            Timber.tag(TAG).i("BT attached: fd=${pfd.fd} mac=$mac")

        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "attachBluetooth error")
            result.addProperty("ok", false)
            result.addProperty("error", e.message ?: "unknown")
        }
        return result.toString()
    }

    // ========== FD 管理 ==========

    /**
     * 释放指定的文件描述符
     */
    fun releaseFd(fd: Int): Boolean {
        return try {
            synchronized(openDescriptors) {
                openDescriptors[fd]?.close()
                openDescriptors.remove(fd)
            }
            Timber.tag(TAG).d("Released fd=$fd")
            true
        } catch (e: Exception) {
            Timber.tag(TAG).w(e, "releaseFd failed: $fd")
            false
        }
    }

    private fun releaseAll() {
        synchronized(openDescriptors) {
            for ((k, v) in openDescriptors) {
                try { v.close() } catch (_: Exception) {}
            }
            openDescriptors.clear()
        }
        try {
            (currentUsbConnection as? android.hardware.usb.UsbDeviceConnection)?.close()
        } catch (_: Exception) {}
        try { bluetoothSocket?.close() } catch (_: Exception) {}
        currentUsbConnection = null
        bluetoothSocket = null
        serverModule = null
        Timber.tag(TAG).d("All resources released")
    }

    // ========== Python 初始化 ==========

    /**
     * 初始化 Python 运行时
     */
    @Synchronized
    private fun initPython(context: Context) {
        if (Python.isStarted()) {
            Timber.tag(TAG).v("Python already started")
            python = Python.getInstance()
            return
        }
        try {
            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(context))
            }
            python = Python.getInstance()
            Timber.tag(TAG).i("Python runtime started: ${python?.version}")
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Python init failed")
            throw e
        }
    }

    /**
     * 获取 run.py 模块引用
     */
    private fun getServerModule(): PyObject? {
        if (serverModule != null) return serverModule

        try {
            val py = python ?: throw IllegalStateException("Python not initialized")
            serverModule = py.getModule(MODULE_NAME)
            return serverModule
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "getServerModule failed")
            return null
        }
    }

    /**
     * 注入运行时配置 (数据目录、Android context)
     */
    private fun injectConfig(context: Context, port: Int) {
        try {
            val appDir = context.filesDir.absolutePath
            val logDir = File(context.filesDir, "logs").apply { mkdirs() }.absolutePath
            val pyDataDir = File(context.filesDir, "cashier_data").apply { mkdirs() }.absolutePath
            dataDir = pyDataDir

            val module = getServerModule()
            module?.callAttr("set_android_context", mapOf(
                "data_dir" to pyDataDir,
                "log_dir" to logDir,
                "app_dir" to appDir,
                "port" to port,
                "platform" to "android"
            ))

            Timber.tag(TAG).i("Config injected: data_dir=$pyDataDir port=$port")
        } catch (e: Exception) {
            Timber.tag(TAG).w(e, "injectConfig failed", e)
        }
    }
}

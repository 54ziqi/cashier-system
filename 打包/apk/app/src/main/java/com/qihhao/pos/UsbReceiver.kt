package com.qihhao.pos

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.os.Build
import timber.log.Timber

/**
 * USB 设备插拔广播接收器
 *
 * 监听 USB_DEVICE_ATTACHED / USB_DEVICE_DETACHED 事件，
 * 由 MainActivity 或 Service 实例化并注册。
 *
 * 子类需覆写 onUsbDeviceAttached / onUsbDeviceDetached 进行业务处理。
 */
abstract class UsbReceiver : BroadcastReceiver() {

    abstract fun onUsbDeviceAttached(device: UsbDevice)
    abstract fun onUsbDeviceDetached(device: UsbDevice)

    override fun onReceive(context: Context?, intent: Intent?) {
        if (intent == null || context == null) return

        val action = intent.action ?: return
        Timber.tag("UsbReceiver").v("onReceive: $action")

        val device: UsbDevice? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, UsbDevice::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(UsbManager.EXTRA_DEVICE)
        }

        if (device == null) {
            Timber.tag("UsbReceiver").w("No device in intent: $action")
            return
        }

        when (action) {
            UsbManager.ACTION_USB_DEVICE_ATTACHED -> {
                Timber.tag("UsbReceiver").i(
                    "USB ATTACHED: vid=${device.vendorId} pid=${device.productId} name=${device.deviceName}"
                )
                onUsbDeviceAttached(device)
            }
            UsbManager.ACTION_USB_DEVICE_DETACHED -> {
                Timber.tag("UsbReceiver").i(
                    "USB DETACHED: vid=${device.vendorId} pid=${device.productId} name=${device.deviceName}"
                )
                onUsbDeviceDetached(device)
            }
            MainActivity.USB_PERMISSION_ACCESS -> {
                val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
                Timber.tag("UsbReceiver").i("USB permission granted=$granted for vid=${device.vendorId} pid=${device.productId}")
                if (granted) {
                    onUsbDeviceAttached(device)
                }
            }
        }
    }
}

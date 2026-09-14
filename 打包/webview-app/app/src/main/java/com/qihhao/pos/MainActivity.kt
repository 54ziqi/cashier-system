package com.qihhao.pos

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.*
import androidx.appcompat.app.AppCompatActivity
import com.google.gson.Gson
import com.google.gson.JsonParser

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val gson = Gson()

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        webView = WebView(this).apply {
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                allowFileAccess = true
                allowContentAccess = true
                mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                setSupportZoom(false)
                builtInZoomControls = false
                displayZoomControls = false
                useWideViewPort = true
                loadWithOverviewMode = true
                cacheMode = WebSettings.LOAD_DEFAULT
            }
            webViewClient = LocalWebViewClient()
            addJavascriptInterface(WebApiBridge(), "NativeAPI")
        }
        setContentView(webView)
        webView.loadUrl("file:///android_asset/www/index.html")
    }

    inner class LocalWebViewClient : WebViewClient() {
        override fun onPageFinished(view: WebView?, url: String?) {
            super.onPageFinished(view, url)
            view?.evaluateJavascript(
                "(function(){" +
                "if(window.__fetch_patched__)return;" +
                "window.__fetch_patched__=true;" +
                "var of=window.fetch;" +
                "window.fetch=function(u,o){" +
                "o=o||{};" +
                "if(typeof u==='string'&&(u.indexOf('/api/')===0||u.indexOf('/auth/')===0)){" +
                "try{" +
                "var m=(o.method||'GET').toUpperCase();" +
                "var b=o.body||null;" +
                "var t=localStorage.getItem('token')||'';" +
                "var h={'Content-Type':'application/json'};" +
                "if(t)h['Authorization']='Bearer '+t;" +
                "var raw=window.NativeAPI.request(JSON.stringify({method:m,path:u,body:b,headers:h}));" +
                "var p=JSON.parse(raw);" +
                "return Promise.resolve(new Response(JSON.stringify(p.body),{status:p.status}));"+
                "}catch(e){return Promise.reject(new Error('bridge error: '+e.message));}}" +
                "return of.apply(window,arguments);};" +
                "})();", null)
        }
    }

    inner class WebApiBridge {
        @JavascriptInterface
        fun request(payload: String): String {
            return try {
                val json = JsonParser.parseString(payload).asJsonObject
                val method = json.get("method")?.asString ?: "GET"
                val path = json.get("path")?.asString ?: "/"
                handleApi(method, path)
            } catch (e: Exception) {
                gson.toJson(mapOf("status" to 400, "statusText" to "Bad Request", "body" to """{"detail":"${e.message}"}"""))
            }
        }
    }

    private fun handleApi(method: String, path: String): String {
        val body = when {
            path == "/auth/login" && method == "POST" -> """{"access_token":"android-demo-token","token_type":"bearer","user":{"username":"demo","role":"cashier","display_name":"演示账号"}}"""
            path == "/auth/me" -> """{"username":"demo","role":"cashier","display_name":"演示账号"}"""
            path == "/tables" -> """{"tables":$TABLES}"""
            path == "/products" -> """{"products":$PRODUCTS}"""
            path == "/orders" && method == "POST" -> """{"order_id":"DEMO${(1000..9999).random()}","status":"pending","message":"订单创建成功(演示模式)"}"""
            path == "/orders" -> """{"orders":[]}"""
            path == "/orders/active" -> """{"tables":{}}"""
            path == "/orders/kitchen" -> """{"orders":[]}"""
            path.startsWith("/orders/") -> """{"order_id":"${path.removePrefix("/orders/")}","status":"active","items":[]}"""
            path == "/dashboard/summary" -> DASHBOARD
            path == "/reports/sales" -> """{"daily_summary":[],"total":0}"""
            path == "/members/search" -> """{"members":[]}"""
            else -> """{"detail":"$method $path"}"""
        }
        val code = if (path.startsWith("/auth/login") && method == "POST") 200
        else if (path.startsWith("/orders") && method == "POST") 201
        else if (path == "/auth/me") 200
        else 200
        return gson.toJson(mapOf("status" to code, "statusText" to "OK", "body" to body))
    }

    companion object {
        val TABLES = """[
          {"id":"T1","name":"A1","status":"empty","seats":4,"order_id":null},
          {"id":"T2","name":"A2","status":"empty","seats":4,"order_id":null},
          {"id":"T3","name":"A3","status":"occupied","seats":2,"order_id":"demo001"},
          {"id":"T4","name":"B1","status":"empty","seats":6,"order_id":null},
          {"id":"T5","name":"B2","status":"reserved","seats":4,"order_id":null},
          {"id":"T6","name":"C1","status":"empty","seats":8,"order_id":null}
        ]"""

        val PRODUCTS = """[
          {"id":"P001","name":"拿铁","category":"coffee","price":28.0,"stock":88,"spec_options":[{"name":"规格","options":[{"label":"中杯","delta":0},{"label":"大杯","delta":6}]},{"name":"温度","options":[{"label":"热","delta":0},{"label":"冰","delta":0}]}]},
          {"id":"P002","name":"美式","category":"coffee","price":22.0,"stock":99,"spec_options":[{"name":"规格","options":[{"label":"中杯","delta":0},{"label":"大杯","delta":5}]}]},
          {"id":"P003","name":"芝士蛋糕","category":"dessert","price":38.0,"stock":20},
          {"id":"P004","name":"三明治","category":"food","price":32.0,"stock":15},
          {"id":"P005","name":"龙井奶茶","category":"tea","price":24.0,"stock":45,"spec_options":[{"name":"甜度","options":[{"label":"无糖","delta":0},{"label":"少糖","delta":0},{"label":"正常","delta":0}]},{"name":"冰度","options":[{"label":"去冰","delta":0},{"label":"少冰","delta":0},{"label":"正常冰","delta":0}]}]}
        ]"""

        val DASHBOARD = """{"today_orders":12,"today_revenue":1288.50,"today_avg_ticket":107.38,"pending_orders":3,"active_table_count":4,"total_tables":6,"alerts":[{"type":"low_stock","message":"芝士蛋糕库存偏低(20)","level":"warn"}]}"""
    }
}

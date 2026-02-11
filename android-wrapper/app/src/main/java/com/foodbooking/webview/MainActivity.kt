package com.foodbooking.webview

import android.annotation.SuppressLint
import android.content.Intent
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private lateinit var webView: WebView
    private lateinit var offlineView: LinearLayout
    private lateinit var connectivityManager: ConnectivityManager
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        offlineView = findViewById(R.id.offline_view)
        webView.webViewClient = WebViewClient()
        webView.webChromeClient = WebChromeClient()
        webView.settings.javaScriptEnabled = true
        webView.settings.domStorageEnabled = true
        setupOfflineActions()
        connectivityManager = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
        updateConnectivityState()
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onStart() {
        super.onStart()
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        networkCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                runOnUiThread { updateConnectivityState() }
            }

            override fun onLost(network: Network) {
                runOnUiThread { updateConnectivityState() }
            }
        }
        connectivityManager.registerNetworkCallback(request, networkCallback!!)
    }

    override fun onStop() {
        super.onStop()
        networkCallback?.let { connectivityManager.unregisterNetworkCallback(it) }
        networkCallback = null
    }

    private fun setupOfflineActions() {
        findViewById<Button>(R.id.offline_retry).setOnClickListener {
            updateConnectivityState()
        }
        findViewById<Button>(R.id.offline_settings).setOnClickListener {
            startActivity(Intent(Settings.ACTION_WIFI_SETTINGS))
        }
    }

    private fun updateConnectivityState() {
        if (isOnline()) {
            offlineView.visibility = View.GONE
            webView.visibility = View.VISIBLE
            if (webView.url == null) {
                webView.loadUrl(getString(R.string.web_url))
            } else {
                webView.reload()
            }
        } else {
            webView.visibility = View.GONE
            offlineView.visibility = View.VISIBLE
        }
    }

    private fun isOnline(): Boolean {
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }
}

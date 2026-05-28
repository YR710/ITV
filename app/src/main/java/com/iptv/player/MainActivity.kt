package com.iptv.player

import android.os.Bundle
import android.view.View
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.exoplayer2.MediaItem
import com.google.android.exoplayer2.SimpleExoPlayer
import com.google.android.exoplayer2.source.hls.HlsMediaSource
import com.google.android.exoplayer2.trackselection.DefaultTrackSelector
import com.google.android.exoplayer2.ui.PlayerView
import com.google.android.exoplayer2.upstream.DefaultHttpDataSource
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {

    private lateinit var playerView: PlayerView
    private lateinit var loadingSpinner: ProgressBar
    private lateinit var errorText: TextView
    private lateinit var channelList: RecyclerView
    private var exoPlayer: SimpleExoPlayer? = null
    private var currentChannelUrl: String? = null
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        playerView = findViewById(R.id.player_view)
        loadingSpinner = findViewById(R.id.loading_spinner)
        errorText = findViewById(R.id.error_text)
        channelList = findViewById(R.id.channel_list)

        channelList.layoutManager = LinearLayoutManager(this)

        // 获取播放列表地址
        val baseUrl = BuildConfig.BASE_URL
        val m3uUrl = if (baseUrl.endsWith("/")) baseUrl + "tv.m3u" else baseUrl + "/tv.m3u"
        val txtUrl = if (baseUrl.endsWith("/")) baseUrl + "tv.txt" else baseUrl + "/tv.txt"
        
        // 优先加载 M3U，失败则加载 TXT
        loadPlaylist(m3uUrl, true) { success ->
            if (!success) {
                loadPlaylist(txtUrl, false) { txtSuccess ->
                    if (!txtSuccess) {
                        runOnUiThread {
                            loadingSpinner.visibility = View.GONE
                            errorText.text = "无法加载播放列表\n请检查网络或源地址\n\n尝试加载的地址:\n$m3uUrl\n$txtUrl"
                            errorText.visibility = View.VISIBLE
                        }
                    }
                }
            }
        }
    }

    private fun loadPlaylist(url: String, isM3u: Boolean, callback: (Boolean) -> Unit) {
        runOnUiThread {
            loadingSpinner.visibility = View.VISIBLE
            errorText.visibility = View.GONE
        }

        Thread {
            try {
                val request = Request.Builder().url(url).build()
                val response = client.newCall(request).execute()
                
                if (!response.isSuccessful) {
                    callback(false)
                    return@Thread
                }
                
                val content = response.body?.string() ?: ""
                val channels = if (isM3u) parseM3u(content) else parseTxt(content)
                
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    if (channels.isEmpty()) {
                        errorText.text = "未找到任何频道"
                        errorText.visibility = View.VISIBLE
                        callback(false)
                    } else {
                        setupChannelList(channels)
                        playChannel(channels[0].url)
                        callback(true)
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    errorText.text = "加载失败: ${e.message}"
                    errorText.visibility = View.VISIBLE
                }
                callback(false)
            }
        }.start()
    }

    private fun parseM3u(content: String): List<Channel> {
        val channels = mutableListOf<Channel>()
        var currentName = ""
        
        content.lines().forEach { line ->
            val trimmed = line.trim()
            when {
                trimmed.startsWith("#EXTINF") -> {
                    val idx = trimmed.lastIndexOf(",")
                    if (idx != -1) currentName = trimmed.substring(idx + 1).trim()
                }
                trimmed.startsWith("http") && currentName.isNotEmpty() -> {
                    channels.add(Channel(currentName, trimmed))
                    currentName = ""
                }
            }
        }
        return channels
    }

    private fun parseTxt(content: String): List<Channel> {
        val channels = mutableListOf<Channel>()
        content.lines().forEach { line ->
            val trimmed = line.trim()
            if (trimmed.isNotEmpty() && !trimmed.startsWith("#")) {
                val comma = trimmed.indexOf(',')
                if (comma > 0) {
                    val name = trimmed.substring(0, comma)
                    val url = trimmed.substring(comma + 1)
                    if (url.startsWith("http")) {
                        channels.add(Channel(name, url))
                    }
                }
            }
        }
        return channels
    }

    private fun setupChannelList(channels: List<Channel>) {
        val adapter = object : RecyclerView.Adapter<RecyclerView.ViewHolder>() {
            override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
                val tv = TextView(parent.context).apply {
                    layoutParams = ViewGroup.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT,
                        ViewGroup.LayoutParams.WRAP_CONTENT
                    )
                    setPadding(50, 30, 50, 30)
                    textSize = 16f
                    setTextColor(0xFFFFFFFF.toInt())
                }
                return object : RecyclerView.ViewHolder(tv) {}
            }

            override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
                val channel = channels[position]
                (holder.itemView as TextView).text = channel.name
                holder.itemView.setOnClickListener { playChannel(channel.url) }
            }

            override fun getItemCount() = channels.size
        }
        channelList.adapter = adapter
    }

    private fun playChannel(url: String) {
        if (currentChannelUrl == url && exoPlayer?.isPlaying == true) return
        currentChannelUrl = url

        releasePlayer()
        val trackSelector = DefaultTrackSelector(this)
        exoPlayer = SimpleExoPlayer.Builder(this).setTrackSelector(trackSelector).build()
        playerView.player = exoPlayer

        val mediaSource = HlsMediaSo
        playerView = findViewById(R.id.player_view)
        loadingSpinner = findViewById(R.id.loading_spinner)
        errorText = findViewById(R.id.error_text)
        channelList = findViewById(R.id.channel_list)

        channelList.layoutManager = LinearLayoutManager(this)

        val baseUrl = BuildConfig.BASE_URL
        val baseDir = if (baseUrl.contains("/")) {
            if (baseUrl.endsWith("/")) baseUrl else baseUrl.substringBeforeLast("/") + "/"
        } else {
            baseUrl + "/"
        }
        
        loadPlaylistWithFallback(baseDir)
    }

    private fun loadPlaylistWithFallback(baseDir: String) {
        loadChannelList("${baseDir}tv.m3u", isM3uFormat = true) { success ->
            if (!success) {
                println("M3U 加载失败，尝试 TXT 格式...")
                loadChannelList("${baseDir}tv.txt", isM3uFormat = false) { txtSuccess ->
                    if (!txtSuccess) {
                        runOnUiThread {
                            loadingSpinner.visibility = View.GONE
                            errorText.text = "无法加载播放列表\n请检查网络或源地址"
                            errorText.visibility = View.VISIBLE
                            Toast.makeText(this@MainActivity, "M3U 和 TXT 格式均加载失败", Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
        }
    }

    private fun loadChannelList(playlistUrl: String, isM3uFormat: Boolean, onResult: (Boolean) -> Unit) {
        runOnUiThread {
            loadingSpinner.visibility = View.VISIBLE
            errorText.visibility = View.GONE
        }
        
        println("=== IPTV Debug ===")
        println("尝试加载: $playlistUrl")
        println("格式类型: ${if (isM3uFormat) "M3U" else "TXT"}")

        Thread {
            try {
                val request = Request.Builder().url(playlistUrl).build()
                val response = client.newCall(request).execute()
                println("HTTP 状态码: ${response.code}")
                
                if (!response.isSuccessful) {
                    onResult(false)
                    return@Thread
                }
                
                val content = response.body?.string() ?: ""
                println("下载内容长度: ${content.length} 字符")
                
                val channels = if (isM3uFormat) {
                    parseM3uPlaylist(content)
                } else {
                    parseTxtPlaylist(content)
                }
                
                println("解析到频道数量: ${channels.size}")
                
                if (channels.isEmpty()) {
                    onResult(false)
                    return@Thread
                }
                
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    setupChannelList(channels)
                    if (channels.isNotEmpty()) {
                        println("尝试播放第一个频道: ${channels[0].name} - ${channels[0].url}")
                        playChannel(channels[0].url)
                    }
                }
                onResult(true)
            } catch (e: Exception) {
                e.printStackTrace()
                println("加载失败: ${e.message}")
                onResult(false)
            }
        }.start()
    }

    private fun parseM3uPlaylist(content: String): List<Channel> {
        val lines = content.lines()
        val channels = mutableListOf<Channel>()
        var currentName = ""
        
        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isEmpty()) continue
            
            if (trimmed.startsWith("#EXTINF")) {
                val nameStart = trimmed.lastIndexOf(",")
                if (nameStart != -1) {
                    currentName = trimmed.substring(nameStart + 1).trim()
                }
            } else if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
                if (currentName.isNotEmpty()) {
                    channels.add(Channel(currentName, trimmed))
                    currentName = ""
                }
            }
        }
        
        return channels
    }

    private fun parseTxtPlaylist(content: String): List<Channel> {
        val lines = content.lines()
        val channels = mutableListOf<Channel>()
        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isEmpty() || trimmed.startsWith("#")) continue
            val commaIndex = trimmed.indexOf(',')
            if (commaIndex > 0) {
                val name = trimmed.substring(0, commaIndex)
                val url = trimmed.substring(commaIndex + 1)
                if (url.startsWith("http")) {
                    channels.add(Channel(name, url))
                }
            }
        }
        return channels
    }

    private fun setupChannelList(channels: List<Channel>) {
        val adapter = ChannelAdapter(channels) { channel ->
            playChannel(channel.url)
        }
        channelList.adapter = adapter
    }

    private fun playChannel(url: String) {
        if (currentChannelUrl == url && exoPlayer?.isPlaying == true) return
        currentChannelUrl = url

        releasePlayer()
        val trackSelector = DefaultTrackSelector(this)
        exoPlayer = SimpleExoPlayer.Builder(this).setTrackSelector(trackSelector).build()
        playerView.player = exoPlayer

        val dataSourceFactory = DefaultHttpDataSource.Factory()
        val mediaSource = HlsMediaSource.Factory(dataSourceFactory)
            .createMediaSource(MediaItem.fromUri(url))
        exo
        playerView = findViewById(R.id.player_view)
        loadingSpinner = findViewById(R.id.loading_spinner)
        errorText = findViewById(R.id.error_text)
        channelList = findViewById(R.id.channel_list)

        channelList.layoutManager = LinearLayoutManager(this)

        // 获取基础 URL
        val baseUrl = BuildConfig.BASE_URL
        val baseDir = if (baseUrl.contains("/")) {
            if (baseUrl.endsWith("/")) baseUrl else baseUrl.substringBeforeLast("/") + "/"
        } else {
            baseUrl + "/"
        }
        
        // 优先尝试 M3U，失败则尝试 TXT
        loadPlaylistWithFallback(baseDir)
    }

    private fun loadPlaylistWithFallback(baseDir: String) {
        loadChannelList("${baseDir}tv.m3u", isM3uFormat = true) { success ->
            if (!success) {
                println("M3U 加载失败，尝试 TXT 格式...")
                loadChannelList("${baseDir}tv.txt", isM3uFormat = false) { txtSuccess ->
                    if (!txtSuccess) {
                        runOnUiThread {
                            loadingSpinner.visibility = View.GONE
                            errorText.text = "无法加载播放列表\n请检查网络或源地址"
                            errorText.visibility = View.VISIBLE
                            Toast.makeText(this@MainActivity, "M3U 和 TXT 格式均加载失败", Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
        }
    }

    private fun loadChannelList(playlistUrl: String, isM3uFormat: Boolean, onResult: (Boolean) -> Unit) {
        runOnUiThread {
            loadingSpinner.visibility = View.VISIBLE
            errorText.visibility = View.GONE
        }
        
        println("=== IPTV Debug ===")
        println("尝试加载: $playlistUrl")
        println("格式类型: ${if (isM3uFormat) "M3U" else "TXT"}")

        thread {
            try {
                val request = Request.Builder().url(playlistUrl).build()
                val response = client.newCall(request).execute()
                println("HTTP 状态码: ${response.code}")
                
                if (!response.isSuccessful) {
                    onResult(false)
                    return@thread
                }
                
                val content = response.body?.string() ?: ""
                println("下载内容长度: ${content.length} 字符")
                
                val channels = if (isM3uFormat) {
                    parseM3uPlaylist(content)
                } else {
                    parseTxtPlaylist(content)
                }
                
                println("解析到频道数量: ${channels.size}")
                
                if (channels.isEmpty()) {
                    onResult(false)
                    return@thread
                }
                
                runOnUiThread {
                    loadingSpinner.visibility = View.GONE
                    setupChannelList(channels)
                    if (channels.isNotEmpty()) {
                        println("尝试播放第一个频道: ${channels[0].name} - ${channels[0].url}")
                        playChannel(channels[0].url)
                    }
                }
                onResult(true)
            } catch (e: Exception) {
                e.printStackTrace()
                println("加载失败: ${e.message}")
                onResult(false)
            }
        }
    }

    private fun parseM3uPlaylist(content: String): List<Channel> {
        val lines = content.lines()
        val channels = mutableListOf<Channel>()
        var currentName = ""
        
        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isEmpty()) continue
            
            if (trimmed.startsWith("#EXTINF")) {
                val nameStart = trimmed.lastIndexOf(",")
                if (nameStart != -1) {
                    currentName = trimmed.substring(nameStart + 1).trim()
                }
            } else if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
                if (currentName.isNotEmpty()) {
                    channels.add(Channel(currentName, trimmed))
                    currentName = ""
                }
            }
        }
        
        return channels
    }

    private fun parseTxtPlaylist(content: String): List<Channel> {
        val lines = content.lines()
        val channels = mutableListOf<Channel>()
        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isEmpty() || trimmed.startsWith("#")) continue
            val commaIndex = trimmed.indexOf(',')
            if (commaIndex > 0) {
                val name = trimmed.substring(0, commaIndex)
                val url = trimmed.substring(commaIndex + 1)
                if (url.startsWith("http")) {
                    channels.add(Channel(name, url))
                }
            }
        }
        return channels
    }

    private fun setupChannelList(channels: List<Channel>) {
        val adapter = ChannelAdapter(channels) { channel ->
            playChannel(channel.url)
        }
        channelList.adapter = adapter
    }

    private fun playChannel(url: String) {
        if (currentChannelUrl == url && exoPlayer?.isPlaying == true) return
        currentChannelUrl = url

        releasePlayer()
        val trackSelector = DefaultTrackSelector(this)
        exoPlayer = SimpleExoPlayer.Builder(this).setTrackSelector(trackSelector).build()
        playerView.player = exoPlayer

        val dataSourceFactory = DefaultHttpDataSource.Factory()
        val mediaSource = HlsMediaSource.Factory(dataSo

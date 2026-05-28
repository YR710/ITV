package com.example.tvplayer.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.unit.dp
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.example.tvplayer.data.PlaylistParser
import com.example.tvplayer.playback.PlaybackManager
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun PlayerScreen(
    channelId: Int,
    onBack: () -> Unit,
    isTv: Boolean
) {
    val channels = PlaylistParser.getChannels()
    val currentIndex = channels.indexOfFirst { it.id == channelId }
    val player = remember { PlaybackManager.getInstance().player }
    var isControlsVisible by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    
    // 播放当前频道
    LaunchedEffect(channelId) {
        if (currentIndex != -1) {
            PlaybackManager.getInstance().playChannel(currentIndex)
        }
    }
    
    Box(modifier = Modifier.fillMaxSize()) {
        // ExoPlayer 视图
        AndroidView(
            factory = { context ->
                PlayerView(context).apply {
                    this.player = player
                    useController = true
                    // 设置控制器自动隐藏超时（0 表示不自动隐藏，由触摸控制）
                    setShowTimeoutMs(0)
                    hideOnTouch = false
                }
            },
            modifier = Modifier.fillMaxSize()
        )
        
        // 透明节目单层（点击屏幕时显示）
        if (isControlsVisible) {
            ChannelListOverlay(
                channels = channels,
                currentIndex = currentIndex,
                onChannelSelected = { index ->
                    PlaybackManager.getInstance().playChannel(index)
                    isControlsVisible = false
                },
                onDismiss = { isControlsVisible = false },
                modifier = Modifier.fillMaxSize()
            )
        }
    }
    
    // 监听触摸事件显示/隐藏节目单
    // 实际应在 AndroidView 上设置触摸监听，此处简化
    DisposableEffect(Unit) {
        val playerView = (player.currentMediaItem?.mediaId)
        onDispose { }
    }
}

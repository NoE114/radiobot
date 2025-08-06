import discord
from discord.ext import commands
import asyncio
import yt_dlp
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration - Set your specific channel and guild IDs
TARGET_GUILD_ID = None  # Replace with your server ID (right-click server -> Copy ID)
TARGET_CHANNEL_ID = None  # Replace with your voice channel ID (right-click channel -> Copy ID)
AUTO_JOIN_ON_STARTUP = True  # Set to True to auto-join on bot start

# Radio stations database
RADIO_STATIONS = {
    # Global/International
    'bbc1': 'https://stream.live.vc.bbcmedia.co.uk/bbc_radio_one',
    'bbc2': 'https://stream.live.vc.bbcmedia.co.uk/bbc_radio_two',
    'cnn': 'https://tunein.com/radio/CNN-s2752/',
    
    # US Stations
    'kexp': 'https://kexp-mp3-128.streamguys1.com/kexp128.mp3',
    'npr': 'https://nprdmp.ic.llnwd.net/stream/nprdmp_live01_mp3',
    'kiis': 'https://playerservices.streamtheworld.com/api/livestream-redirect/KIISFMAAC.aac',
    
    # European Stations
    'radio1': 'http://bbcmedia.ic.llnwd.net/stream/bbcmedia_radio1_mf_p',
    'nrj': 'http://cdn.nrjaudio.fm/audio1/fr/30001/mp3_128.mp3',
    
    # Indian Stations
    'radiocity': 'http://prclive1.listenon.in:9960',
    'redFM': 'http://air.pc.cdn.bitgravity.com/air/live/pbaudio043/playlist.m3u8',
    
    # Add more stations as needed
}

# YTDL options for radio streaming
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
        
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Bot events
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # Auto-join the designated voice channel
    if AUTO_JOIN_ON_STARTUP and TARGET_GUILD_ID and TARGET_CHANNEL_ID:
        try:
            guild = bot.get_guild(TARGET_GUILD_ID)
            if guild:
                channel = guild.get_channel(TARGET_CHANNEL_ID)
                if channel and isinstance(channel, discord.VoiceChannel):
                    # Check if already connected to this channel
                    voice_client = guild.voice_client
                    if not voice_client or voice_client.channel.id != TARGET_CHANNEL_ID:
                        if voice_client:
                            await voice_client.disconnect()
                        await channel.connect()
                        print(f'🎵 Auto-joined voice channel: {channel.name}')
                    else:
                        print(f'🎵 Already connected to target channel: {channel.name}')
                else:
                    print(f'❌ Target channel not found or not a voice channel')
            else:
                print(f'❌ Target guild not found')
        except Exception as e:
            print(f'❌ Error auto-joining channel: {e}')
    
    print('🤖 Bot is ready and configured for single-channel operation!')

@bot.event
async def on_voice_state_update(member, before, after):
    """Ensure bot stays in the designated channel"""
    if member == bot.user:
        return
    
    # If bot gets disconnected, try to rejoin the target channel
    if bot.voice_clients:
        voice_client = bot.voice_clients[0]
        if not voice_client.is_connected():
            await auto_rejoin_target_channel()

async def auto_rejoin_target_channel():
    """Automatically rejoin the target channel if disconnected"""
    if TARGET_GUILD_ID and TARGET_CHANNEL_ID:
        try:
            guild = bot.get_guild(TARGET_GUILD_ID)
            if guild:
                channel = guild.get_channel(TARGET_CHANNEL_ID)
                if channel and isinstance(channel, discord.VoiceChannel):
                    await channel.connect()
                    print(f'🔄 Reconnected to target channel: {channel.name}')
        except Exception as e:
            print(f'❌ Error rejoining target channel: {e}')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument. Use `!help` for command usage.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command. Use `!help` to see available commands.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        print(f"Error: {error}")

# Utility function to check if user is in the target channel
def is_in_target_channel(ctx):
    """Check if the user is in the designated voice channel"""
    if not TARGET_CHANNEL_ID:
        return True  # If no target channel set, allow from anywhere
    
    if not ctx.author.voice:
        return False
    
    return ctx.author.voice.channel.id == TARGET_CHANNEL_ID

def is_bot_in_target_channel(ctx):
    """Check if bot is connected to the target channel"""
    if not TARGET_CHANNEL_ID:
        return bool(ctx.voice_client)
    
    return (ctx.voice_client and 
            ctx.voice_client.channel and 
            ctx.voice_client.channel.id == TARGET_CHANNEL_ID)

# Radio commands
@bot.command(name='join', help='Make the bot join the designated voice channel')
async def join(ctx):
    # If target channel is configured, ignore user's channel and join target
    if TARGET_GUILD_ID and TARGET_CHANNEL_ID:
        guild = bot.get_guild(TARGET_GUILD_ID)
        if not guild:
            await ctx.send("❌ Target server not found!")
            return
        
        channel = guild.get_channel(TARGET_CHANNEL_ID)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await ctx.send("❌ Target voice channel not found!")
            return
        
        # Check if already connected to target channel
        if ctx.voice_client and ctx.voice_client.channel.id == TARGET_CHANNEL_ID:
            await ctx.send(f"✅ Already connected to {channel.name}")
            return
        
        # Disconnect from any other channel first
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        
        await channel.connect()
        await ctx.send(f"🎵 Joined designated channel: **{channel.name}**")
        return
    
    # Fallback to original behavior if no target channel configured
    if not ctx.author.voice:
        await ctx.send("❌ You need to be in a voice channel, or configure TARGET_CHANNEL_ID!")
        return
    
    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        return await ctx.voice_client.move_to(channel)
    
    await channel.connect()
    await ctx.send(f"🎵 Joined {channel}")

@bot.command(name='leave', help='Make the bot leave the voice channel (will auto-rejoin if configured)')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left the voice channel")
        
        # Auto-rejoin if configured
        if AUTO_JOIN_ON_STARTUP and TARGET_CHANNEL_ID:
            await asyncio.sleep(2)  # Brief delay
            await auto_rejoin_target_channel()
            await ctx.send("🔄 Auto-rejoined designated channel")
    else:
        await ctx.send("❌ Not connected to a voice channel")

@bot.command(name='play', help='Play a radio station (!play <station_name>)')
async def play(ctx, *, station=None):
    if not station:
        await ctx.send("❌ Please specify a station. Use `!stations` to see available options.")
        return
    
    # Check if target channel is configured and enforce it
    if TARGET_CHANNEL_ID:
        if not is_in_target_channel(ctx):
            channel_name = "the designated channel"
            if TARGET_GUILD_ID:
                guild = bot.get_guild(TARGET_GUILD_ID)
                if guild:
                    channel = guild.get_channel(TARGET_CHANNEL_ID)
                    if channel:
                        channel_name = f"**{channel.name}**"
            await ctx.send(f"❌ You need to be in {channel_name} to control the radio!")
            return
        
        # Ensure bot is in target channel
        if not is_bot_in_target_channel(ctx):
            await ctx.invoke(join)
    else:
        # Original behavior if no target channel configured
        if not ctx.author.voice:
            await ctx.send("❌ You need to be in a voice channel!")
            return
        
        if not ctx.voice_client:
            await ctx.invoke(join)
    
    station_lower = station.lower()
    if station_lower not in RADIO_STATIONS:
        await ctx.send(f"❌ Station '{station}' not found. Use `!stations` to see available stations.")
        return
    
    url = RADIO_STATIONS[station_lower]
    
    try:
        # Stop current playback
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        await ctx.send(f"🔄 Loading station: {station}...")
        
        # Try to play the radio stream
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
            await ctx.send(f"🎵 Now playing: **{station.upper()}**")
        except Exception as e:
            # Fallback: try direct stream
            source = discord.FFmpegPCMAudio(url, **ffmpeg_options)
            ctx.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)
            await ctx.send(f"🎵 Now playing: **{station.upper()}** (direct stream)")
    
    except Exception as e:
        await ctx.send(f"❌ Error playing station: {str(e)}")
        print(f"Play error: {e}")

# Control commands with channel restrictions
@bot.command(name='stop', help='Stop the current radio stream')
async def stop(ctx):
    if TARGET_CHANNEL_ID and not is_in_target_channel(ctx):
        await ctx.send("❌ You need to be in the designated channel to control the radio!")
        return
    
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏹️ Stopped the radio")
    else:
        await ctx.send("❌ Nothing is playing")

@bot.command(name='pause', help='Pause the radio stream')
async def pause(ctx):
    if TARGET_CHANNEL_ID and not is_in_target_channel(ctx):
        await ctx.send("❌ You need to be in the designated channel to control the radio!")
        return
    
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused the radio")
    else:
        await ctx.send("❌ Nothing is playing")

@bot.command(name='resume', help='Resume the radio stream')
async def resume(ctx):
    if TARGET_CHANNEL_ID and not is_in_target_channel(ctx):
        await ctx.send("❌ You need to be in the designated channel to control the radio!")
        return
    
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed the radio")
    else:
        await ctx.send("❌ Nothing is paused")

@bot.command(name='volume', help='Change volume (0-100)')
async def volume(ctx, volume: int = None):
    if TARGET_CHANNEL_ID and not is_in_target_channel(ctx):
        await ctx.send("❌ You need to be in the designated channel to control the radio!")
        return
    
    if not ctx.voice_client:
        await ctx.send("❌ Not connected to a voice channel")
        return
    
    if volume is None:
        current_volume = int(ctx.voice_client.source.volume * 100) if hasattr(ctx.voice_client.source, 'volume') else 50
        await ctx.send(f"🔊 Current volume: {current_volume}%")
        return
    
    if not 0 <= volume <= 100:
        await ctx.send("❌ Volume must be between 0 and 100")
        return
    
    if hasattr(ctx.voice_client.source, 'volume'):
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"🔊 Volume set to {volume}%")
    else:
        await ctx.send("❌ Cannot adjust volume for this stream")

# Add channel configuration commands
@bot.command(name='setchannel', help='Set the designated voice channel (Admin only)')
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    global TARGET_CHANNEL_ID, TARGET_GUILD_ID
    
    if not ctx.author.voice:
        await ctx.send("❌ You need to be in the voice channel you want to set as target!")
        return
    
    TARGET_CHANNEL_ID = ctx.author.voice.channel.id
    TARGET_GUILD_ID = ctx.guild.id
    
    await ctx.send(f"✅ Set **{ctx.author.voice.channel.name}** as the designated radio channel!")
    await ctx.send("🔄 Bot will now auto-join this channel and restrict controls to users in this channel.")
    
    # Auto-join the newly set channel
    if ctx.voice_client and ctx.voice_client.channel.id != TARGET_CHANNEL_ID:
        await ctx.voice_client.move_to(ctx.author.voice.channel)
    elif not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    
    await ctx.send(f"🎵 Joined **{ctx.author.voice.channel.name}**")

@bot.command(name='status', help='Show bot configuration status')
async def status(ctx):
    embed = discord.Embed(title="🤖 Bot Status", color=0x00ff00)
    
    if TARGET_GUILD_ID and TARGET_CHANNEL_ID:
        guild = bot.get_guild(TARGET_GUILD_ID)
        channel_name = "Unknown Channel"
        if guild:
            channel = guild.get_channel(TARGET_CHANNEL_ID)
            if channel:
                channel_name = channel.name
        
        embed.add_field(name="📍 Designated Channel", value=f"**{channel_name}**", inline=False)
        embed.add_field(name="🔧 Mode", value="Single Channel Mode", inline=True)
        embed.add_field(name="🎵 Auto-Join", value="✅ Enabled" if AUTO_JOIN_ON_STARTUP else "❌ Disabled", inline=True)
    else:
        embed.add_field(name="🔧 Mode", value="Free Roam Mode", inline=False)
        embed.add_field(name="📍 Note", value="No designated channel set. Use `!setchannel` to configure.", inline=False)
    
    # Voice connection status
    if ctx.voice_client:
        embed.add_field(name="🔊 Voice Status", value=f"Connected to **{ctx.voice_client.channel.name}**", inline=False)
        if ctx.voice_client.is_playing():
            embed.add_field(name="🎵 Playback", value="▶️ Playing", inline=True)
        elif ctx.voice_client.is_paused():
            embed.add_field(name="🎵 Playback", value="⏸️ Paused", inline=True)
        else:
            embed.add_field(name="🎵 Playback", value="⏹️ Stopped", inline=True)
    else:
        embed.add_field(name="🔊 Voice Status", value="Not connected", inline=False)
    
    await ctx.send(embed=embed)
async def stations(ctx):
    embed = discord.Embed(title="📻 Available Radio Stations", color=0x00ff00)
    
    global_stations = []
    us_stations = []
    eu_stations = []
    indian_stations = []
    
    station_regions = {
        'bbc1': '🌍 Global', 'bbc2': '🌍 Global', 'cnn': '🌍 Global',
        'kexp': '🇺🇸 US', 'npr': '🇺🇸 US', 'kiis': '🇺🇸 US',
        'radio1': '🇪🇺 Europe', 'nrj': '🇪🇺 Europe',
        'radiocity': '🇮🇳 India', 'redfm': '🇮🇳 India'
    }
    
    for station in RADIO_STATIONS.keys():
        region = station_regions.get(station, '🌍 Global')
        if '🌍' in region:
            global_stations.append(f"`{station}` - {region}")
        elif '🇺🇸' in region:
            us_stations.append(f"`{station}` - {region}")
        elif '🇪🇺' in region:
            eu_stations.append(f"`{station}` - {region}")
        elif '🇮🇳' in region:
            indian_stations.append(f"`{station}` - {region}")
    
    if global_stations:
        embed.add_field(name="🌍 Global/International", value="\n".join(global_stations), inline=False)
    if us_stations:
        embed.add_field(name="🇺🇸 United States", value="\n".join(us_stations), inline=False)
    if eu_stations:
        embed.add_field(name="🇪🇺 Europe", value="\n".join(eu_stations), inline=False)
    if indian_stations:
        embed.add_field(name="🇮🇳 India", value="\n".join(indian_stations), inline=False)
    
    embed.add_field(name="Usage", value="Use `!play <station_name>` to play a station", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='now', help='Show currently playing station info')
async def now(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        source = ctx.voice_client.source
        if hasattr(source, 'title') and source.title:
            await ctx.send(f"🎵 Now playing: **{source.title}**")
        else:
            await ctx.send("🎵 Radio is currently playing")
    else:
        await ctx.send("❌ Nothing is playing")

# Help command override
@bot.remove_command('help')
@bot.command(name='help', help='Show this help message')
async def help_command(ctx):
    embed = discord.Embed(title="📻 Radio Bot Commands", color=0x00ff00)
    
    commands_list = [
        ("`!join`", "Join your voice channel"),
        ("`!leave`", "Leave the voice channel"),
        ("`!play <station>`", "Play a radio station"),
        ("`!stop`", "Stop the radio"),
        ("`!pause`", "Pause the radio"),
        ("`!resume`", "Resume the radio"),
        ("`!volume <0-100>`", "Change volume or check current volume"),
        ("`!stations`", "List all available stations"),
        ("`!now`", "Show current playing info"),
        ("`!help`", "Show this help message")
    ]
    
    for command, description in commands_list:
        embed.add_field(name=command, value=description, inline=False)
    
    embed.add_field(name="Example", value="`!play bbc1` - Play BBC Radio 1", inline=False)
    await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    print("Discord Radio Bot")
    print("Setup Instructions:")
    print("1. Install required packages: pip install discord.py[voice] yt-dlp")
    print("2. Install FFmpeg on your system")
    print("3. Replace 'YOUR_BOT_TOKEN' with your actual bot token")
    print("4. Create a bot at https://discord.com/developers/applications")
    print("5. Add the bot to your server with appropriate permissions")
    print("6. OPTIONAL: Set TARGET_GUILD_ID and TARGET_CHANNEL_ID for single-channel mode")
    print("   Or use !setchannel command after bot starts (requires admin permissions)")
    print()
    print("Single-Channel Mode Features:")
    print("- Bot auto-joins designated voice channel on startup")
    print("- Only users in the designated channel can control the radio")
    print("- Bot automatically rejoins if disconnected")
    print("- Use !status to check current configuration")
    print()
    
    # Replace with your bot token
    BOT_TOKEN = 'YOUR_BOT_TOKEN'
    
    if BOT_TOKEN == 'YOUR_BOT_TOKEN':
        print("⚠️  Please set your bot token before running!")
        exit(1)
    
    try:
        bot.run(BOT_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid bot token!")
    except Exception as e:
        print(f"❌ Error running bot: {e}")
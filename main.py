import os
import asyncio
import discord
import urllib
import json
import lxml
import youtube_dl
from pytube import Playlist
from discord.ext import commands
from lxml import etree


# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

BOT_TOKEN = os.getenv("DISCORD_TOKEN")

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
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

queue = {}
now_playing = {}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


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


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(description="joins a voice channel")
    async def join(self, ctx):
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            return await ctx.send("`**You need to be in a voice channel to use this command!**`")

        voice_channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            vc = await voice_channel.connect()
        else:
            await ctx.voice_client.move_to(voice_channel)
            vc = ctx.voice_client


    async def play_queue(self, ctx, url):
        global now_playing
        while len(queue[ctx.message.channel.id]):
            try:
                player = await YTDLSource.from_url(queue[ctx.message.channel.id][0], loop=self.bot.loop, stream=True)
                ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
                now_playing[ctx.author.voice] = player.title
                await ctx.send('```Now playing: {}```'.format(player.title))
                queue[ctx.message.channel.id].pop(0)
            except discord.errors.ClientException: pass
        await ctx.send(f"```Queue ended```")


    @commands.command(description="streams music")
    async def play(self, ctx, *, url):
        global queue
        if ctx.message.channel.id not in queue:
            queue[ctx.message.channel.id] = []

        if len(queue[ctx.message.channel.id]):
            try: queue[ctx.message.channel.id].extend(Playlist(url))
            except: queue[ctx.message.channel.id].append(url)

            print(queue)

            async with ctx.typing():
                await ctx.send(f"```css\n{len(queue[ctx.message.channel.id])} tracks queued\n```")

        else:
            try: queue[ctx.message.channel.id].extend(Playlist(url))
            except: queue[ctx.message.channel.id].append(url)

            async with ctx.typing():
                await ctx.send(f"```css\n{len(queue[ctx.message.channel.id])} tracks queued\n```")

            await self.play_queue(ctx, url)


    @commands.command(description="shows queue")
    async def queue(self, ctx):
        output = ""
        counter = 0
        for i in queue[ctx.message.channel.id]:
            response = urllib.request.urlopen(i)
            response_text = video.read()
            video_data = json.loads(video_text.decode())
            output += f"{queue[ctx.message.channel.id].index(i) + 1} {video_data['title']}\n"
            counter += 1
            if counter == 10: break
        await ctx.send(f"```css\n{output}\n```")


    @commands.command(description="clears queue")
    async def clear(self, ctx):
        global queue
        queue[ctx.message.channel.id] = []
        await ctx.send("```Queue cleared\n```")


    @commands.command(description="stops and disconnects the bot from voice")
    async def leave(self, ctx):
        await ctx.voice_client.disconnect()


    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()


bot = commands.Bot(command_prefix=commands.when_mentioned_or("-"),
                   description='Spizsheno s primera')

@bot.event
async def on_ready():
    print('Logged in as {0} ({0.id})'.format(bot.user))
    print('------')

bot.add_cog(Music(bot))
bot.run(BOT_TOKEN)

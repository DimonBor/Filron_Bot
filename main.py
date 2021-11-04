import os
import re
import asyncio
import discord
import random
import requests
import youtube_dl
from pytube import Playlist
from discord.ext import commands
from bs4 import BeautifulSoup

BOT_TOKEN = os.getenv("DISCORD_TOKEN")

ytdl_format_options = {
    'format': 'worstaudio/worst',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'postprocessor_args': ['-threads', 4],
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
playing = {}
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

        ctx.voice_client.stop()


    async def play_queue(self, ctx):
        global queue, now_playing
        while len(queue[ctx.message.channel.id]):
            channel = bot.get_channel(ctx.message.channel.id)
            historyMessages = await channel.history(limit=100).flatten()
            for messageSearched in historyMessages:
                if now_playing[ctx.message.channel.id] and now_playing[ctx.message.channel.id] in messageSearched.content:
                    await messageSearched.delete()
            player = await YTDLSource.from_url(queue[ctx.message.channel.id][0], loop=self.bot.loop, stream=True)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
            now_playing[ctx.message.channel.id] = player.title
            await ctx.send(f"```css\n[Now playing]\n {player.title}\n```")
            queue[ctx.message.channel.id].pop(0)
            playing = True
            while playing:
                if not ctx.voice_client.is_playing():
                    playing = False
                else:
                    await asyncio.sleep(1)
                    continue
        now_playing[ctx.message.channel.id] = ""
        await ctx.send(f"```diff\n--- Queue ended\n```")


    @commands.command(description="streams music")
    async def play(self, ctx, *, url):
        global queue
        url = re.sub(r'music.', '', url)
        queue[ctx.message.channel.id] = []
        try: queue[ctx.message.channel.id].extend(Playlist(url))
        except: queue[ctx.message.channel.id].append(url)

        async with ctx.typing():
            await ctx.send(f"```diff\n+ {len(queue[ctx.message.channel.id])} tracks queued\n```")

        ctx.voice_client.stop()


    @commands.command(description="adds songs to queue")
    async def add(self, ctx, *, url):
        global queue
        url = re.sub(r'music.', '', url)
        if ctx.message.channel.id not in queue:
            queue[ctx.message.channel.id] = []

        old_len = len(queue[ctx.message.channel.id])

        if len(queue[ctx.message.channel.id]) or ctx.voice_client.is_playing():
            try: queue[ctx.message.channel.id].extend(Playlist(url))
            except: queue[ctx.message.channel.id].append(url)

            async with ctx.typing():
                await ctx.send(f"```diff\n+ {len(queue[ctx.message.channel.id])-old_len} tracks queued\n```")
        else:
            await ctx.send(f"```css\n[The queue is empty send \"-play [arg]\" to start music streaming!]\n```")


    @commands.command(description="shows queue")
    async def queue(self, ctx):
        output = "[Queue]\n"
        counter = 0
        output += f"0. {now_playing[ctx.message.channel.id]} - #now\n"
        for i in queue[ctx.message.channel.id]:
            counter += 1
            try:
                response = requests.get(i)
                response_soup = BeautifulSoup(response.text, "html.parser")
                title = response_soup.find("meta", itemprop="name")["content"]
            except: title = i
            output += f"{queue[ctx.message.channel.id].index(i)+1}. {title}\n"
            if counter == 10: break
        if len(queue[ctx.message.channel.id]) > 10:
            output += "[...]\n"
        output += f"Total queued: {len(queue[ctx.message.channel.id])}"
        async with ctx.typing():
            await ctx.send(f"```css\n{output}\n```")


    @commands.command(description="skips track")
    async def skip(self, ctx):
        ctx.voice_client.stop()


    @commands.command(description="jumps to track by index")
    async def jump(self, ctx, arg1):
        global queue
        try:
            queue[ctx.message.channel.id].insert(0, queue[ctx.message.channel.id][int(arg1)-1])
            queue[ctx.message.channel.id].pop(int(arg1))
        except:
            await ctx.send("```css\n[Invalid Index!]\n```")
            return
        await asyncio.sleep(1)
        ctx.voice_client.stop()


    @commands.command(description="shuffles queue")
    async def shuffle(self, ctx):
        global queue
        random.shuffle(queue[ctx.message.channel.id])
        await ctx.send("```ini\n[Shuffled]\n```")
        ctx.voice_client.stop()


    @commands.command(description="clears queue")
    async def clear(self, ctx):
        global queue
        queue[ctx.message.channel.id] = []
        now_playing[ctx.message.channel.id] = ""
        await ctx.send("```diff\n- Queue cleared\n```")
        await asyncio.sleep(1)
        ctx.voice_client.stop()


    @commands.command(description="stops and disconnects the bot from voice")
    async def leave(self, ctx):
        global queue
        queue[ctx.message.channel.id] = []
        now_playing[ctx.message.channel.id] = ""
        await ctx.voice_client.disconnect()


    @play.after_invoke
    async def check_voice(self, ctx):
        if not now_playing[ctx.message.channel.id]:
            await self.play_queue(ctx)

    @play.before_invoke
    @add.before_invoke
    @shuffle.before_invoke
    @skip.before_invoke
    @jump.before_invoke
    @clear.before_invoke
    @leave.before_invoke
    @queue.before_invoke
    async def ensure_voice(self, ctx):
        if not ctx.author.voice:
            await ctx.send("```css\n[You are not connected to a voice channel]\n```")
            raise commands.CommandError("Author not connected to a voice channel.")
        if ctx.voice_client is None:
            queue[ctx.message.channel.id] = []
            now_playing[ctx.message.channel.id] = ""
            await ctx.author.voice.channel.connect()


bot = commands.Bot(command_prefix=commands.when_mentioned_or("-"),
                   description='Spizsheno s primera')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} ({bot.user.id})')
    print('------')

bot.add_cog(Music(bot))
bot.run(BOT_TOKEN)

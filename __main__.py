import logging
import os
import re
import glob
import asyncio
import discord
import random
import yt_dlp
from discord.ext import commands

BOT_TOKEN = os.getenv("DISCORD_TOKEN")

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'postprocessor_args': ['-threads', 4],
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'verbose': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
    'cookiefile': '/app/cookies.txt'
}

ffmpeg_options = {
    'options': '-vn'
}

queue = {}
now_playing = {}
playing = {}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
discord.utils.setup_logging(level=logging.DEBUG)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, filename, volume=0.5):
        super().__init__(source, volume)

        self.data = data
        self.filename = filename
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url):
        data = ytdl.extract_info(url)

        if 'entries' in data:
            data = data['entries'][0]

        filename = ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, filename=filename)


class Music(commands.Cog, name='Music'):
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
            player = await YTDLSource.from_url(queue[ctx.message.channel.id][0])
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
            now_playing[ctx.message.channel.id] = player.title
            await ctx.send(f"```css\n[Now playing]\n {player.title}\n```")
            queue[ctx.message.channel.id].pop(0)
            while True:
                try:
                    if not ctx.voice_client.is_playing():
                        os.remove(player.filename)
                        break
                    else:
                        await asyncio.sleep(1)
                        continue
                except AttributeError:
                    if len(queue[ctx.message.channel.id]):
                        await ctx.author.voice.channel.connect()
                    break
        now_playing[ctx.message.channel.id] = ""
        await ctx.send(f"```diff\n--- Queue ended\n```")

    @commands.command(description="streams music")
    async def play(self, ctx, *, url):
        global queue
        url = re.sub(r'music.', '', url)
        queue[ctx.message.channel.id] = []
        try:
            playlist_opts = {
                    'quiet': True,
                    'extract_flat': True,
                    'skip_download': True,
                    'cookiefile': '/app/cookies.txt'
                }
            with yt_dlp.YoutubeDL(playlist_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                entries = [entry['url'] for entry in info_dict.get('entries', [])]
                if not entries:
                    raise Exception
                queue[ctx.message.channel.id].extend(entries)
        except Exception:
            queue[ctx.message.channel.id].append(url)

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
            try:
                playlist_opts = {
                    'quiet': True,
                    'extract_flat': True,
                    'skip_download': True,
                    'cookiefile': '/app/cookies.txt'
                }
                with yt_dlp.YoutubeDL(playlist_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
                    entries = [entry['url'] for entry in info_dict.get('entries', [])]
                    if not entries:
                        raise Exception
                    queue[ctx.message.channel.id].extend(entries)
            except Exception:
                queue[ctx.message.channel.id].append(url)

            async with ctx.typing():
                await ctx.send(f"```diff\n+ {len(queue[ctx.message.channel.id]) - old_len} tracks queued\n```")
        else:
            await ctx.send(f"```css\n[The queue is empty send \"-play [arg]\" to start music streaming!]\n```")

    @commands.command(description="shows queue")
    async def queue(self, ctx):
        global queue, now_playing
        output = "[Queue]\n"
        counter = 0
        output += f"0. {now_playing[ctx.message.channel.id]} - #now\n"
        async with ctx.typing():
            for i in queue[ctx.message.channel.id]:
                counter += 1
                try:
                    info_opts = {
                        'quiet': True,
                        'skip_download': True,
                        'cookiefile': '/app/cookies.txt'
                    }
                    with yt_dlp.YoutubeDL(info_opts) as ydl:
                        info = ydl.extract_info(i, download=False)
                        title = info['title']
                except Exception:
                    title = i
                output += f"{queue[ctx.message.channel.id].index(i) + 1}. {title}\n"
                if counter == 10: break
            if len(queue[ctx.message.channel.id]) > 10:
                output += "[...]\n"
            output += f"Total queued: {len(queue[ctx.message.channel.id])}"
            await ctx.send(f"```css\n{output}\n```")

    @commands.command(description="skips track")
    async def skip(self, ctx):
        ctx.voice_client.stop()

    @commands.command(description="jumps to track by index")
    async def jump(self, ctx, arg1):
        global queue
        try:
            queue[ctx.message.channel.id].insert(0, queue[ctx.message.channel.id][int(arg1) - 1])
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
        global queue, now_playing
        queue[ctx.message.channel.id] = []
        now_playing[ctx.message.channel.id] = ""
        await ctx.send("```diff\n- Queue cleared\n```")
        await asyncio.sleep(1)
        ctx.voice_client.stop()

    @commands.command(description="stops and disconnects the bot from voice")
    async def leave(self, ctx):
        global queue, now_playing
        queue[ctx.message.channel.id] = []
        now_playing[ctx.message.channel.id] = ""
        await ctx.voice_client.disconnect()

    @play.after_invoke
    async def check_voice(self, ctx):
        global now_playing
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
        global queue, now_playing
        if not ctx.author.voice:
            await ctx.send("```css\n[You are not connected to a voice channel]\n```")
            raise commands.CommandError("Author not connected to a voice channel.")
        if ctx.voice_client is None:
            queue[ctx.message.channel.id] = []
            now_playing[ctx.message.channel.id] = ""
            await ctx.author.voice.channel.connect()


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='-',
                   description='Szhizo bard',
                   intents=intents)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} ({bot.user.id})')
    print('------')


async def main():
    for f in glob.glob("youtube*.webm"):
        os.remove(f)
    await bot.add_cog(Music(bot))
    await bot.start(BOT_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
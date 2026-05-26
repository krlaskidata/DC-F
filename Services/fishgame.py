import asyncio
import discord
from discord.ext import commands
from discord.ui import View
from collections import defaultdict

FISH_SPAWN_THRESHOLD = 200


class FishButton(View):
    def __init__(self, leaderboard):
        super().__init__(timeout=30)
        self.leaderboard = leaderboard
        self.already_caught = False

    @discord.ui.button(label="Catch", style=discord.ButtonStyle.green)
    async def catch_fish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.already_caught:
            await interaction.response.send_message("Someone already caught the fish!", ephemeral=True)
            return
        self.already_caught = True
        self.leaderboard[interaction.user.id] += 1
        await interaction.response.edit_message(
            content=f"{interaction.user.mention} caught the fish! Total catches: {self.leaderboard[interaction.user.id]}",
            view=None,
        )


class FishCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fish_spawned = False
        self.fish_spawn_lock = asyncio.Lock()
        self.fish_leaderboard = defaultdict(int)
        self.message_count = 0

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        self.message_count += 1
        if self.message_count >= FISH_SPAWN_THRESHOLD and not self.fish_spawned:
            self.message_count = 0
            await self.try_spawn_fish(message.channel)

    async def try_spawn_fish(self, channel):
        if self.fish_spawned:
            return
        async with self.fish_spawn_lock:
            self.fish_spawned = True
            fish_view = FishButton(self.fish_leaderboard)
            await channel.send("A wild fish has appeared! Be the first to catch it!", view=fish_view)
            await asyncio.sleep(50)
            if not fish_view.already_caught:
                await channel.send("The fish escaped...")
            self.fish_spawned = False


async def setup(bot):
    await bot.add_cog(FishCog(bot))
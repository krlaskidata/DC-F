import discord
import json
from discord.ext import commands
from pathlib import Path
from datetime import datetime

DATA_FILE = "xp_data.json"

LEVEL_TIERS = {
    "Recruit": (1, 20),
    "Soldier": (21, 40),
    "Sergeant": (41, 60),
    "Lieutenant": (61, 80),
    "Captain": (81, 100),
}

MESSAGE_ROLES = {
    "Chatty": 100,
    "Talkative": 500,
    "Verbose": 1500,
    "Eloquent": 3000,
    "Legendary Talker": 6000,
}

VOICE_ROLES = {
    "Voice Novice": 10 * 60,
    "Voice Enthusiast": 50 * 60,
    "Voice Regular": 200 * 60,
    "Voice Expert": 500 * 60,
    "Voice Legend": 1000 * 60,
}


class UserXPData:
    def __init__(self):
        self.message_count = 0
        self.message_xp = 0
        self.voice_minutes = 0
        self.voice_xp = 0
        self.total_xp = 0
        self.level = 1
        self.voice_join_time = None

    def to_dict(self):
        return {
            "message_count": self.message_count,
            "message_xp": self.message_xp,
            "voice_minutes": self.voice_minutes,
            "voice_xp": self.voice_xp,
            "total_xp": self.total_xp,
            "level": self.level,
        }

    @staticmethod
    def from_dict(data):
        user = UserXPData()
        user.message_count = data.get("message_count", 0)
        user.message_xp = data.get("message_xp", 0)
        user.voice_minutes = data.get("voice_minutes", 0)
        user.voice_xp = data.get("voice_xp", 0)
        user.total_xp = data.get("total_xp", 0)
        user.level = data.get("level", 1)
        return user


class XPCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_data = self._load_data()

    def _load_data(self):
        if Path(DATA_FILE).exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return {k: UserXPData.from_dict(v) for k, v in raw.items()}
        return {}

    def _save_data(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({k: v.to_dict() for k, v in self.user_data.items()}, f, indent=2)

    def _get_user_data(self, user_id: int) -> UserXPData:
        key = str(user_id)
        if key not in self.user_data:
            self.user_data[key] = UserXPData()
        return self.user_data[key]

    def _calculate_message_xp(self, count: int) -> int:
        return (count * 5) + (count // 100) * 20

    def _calculate_voice_xp(self, minutes: int) -> int:
        hours = minutes // 60
        return (hours * 5) + (hours // 10) * 20

    def _calculate_level(self, xp: int) -> int:
        return max(1, xp // 100)

    def _get_level_tier(self, level: int) -> str:
        for tier, (min_level, max_level) in LEVEL_TIERS.items():
            if min_level <= level <= max_level:
                return tier
        return "Captain"

    def _get_message_role(self, count: int) -> str:
        for role, threshold in sorted(MESSAGE_ROLES.items(), key=lambda x: x[1], reverse=True):
            if count >= threshold:
                return role
        return None

    def _get_voice_role(self, minutes: int) -> str:
        for role, threshold in sorted(VOICE_ROLES.items(), key=lambda x: x[1], reverse=True):
            if minutes >= threshold:
                return role
        return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        user_data = self._get_user_data(message.author.id)
        user_data.message_count += 1
        user_data.message_xp = self._calculate_message_xp(user_data.message_count)
        user_data.total_xp = user_data.message_xp + user_data.voice_xp
        user_data.level = self._calculate_level(user_data.total_xp)

        self._save_data()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        user_data = self._get_user_data(member.id)

        if after.channel and not before.channel:
            user_data.voice_join_time = datetime.now()
        elif before.channel and not after.channel:
            if user_data.voice_join_time:
                duration = datetime.now() - user_data.voice_join_time
                user_data.voice_minutes += int(duration.total_seconds() // 60)
                user_data.voice_xp = self._calculate_voice_xp(user_data.voice_minutes)
                user_data.total_xp = user_data.message_xp + user_data.voice_xp
                user_data.level = self._calculate_level(user_data.total_xp)
                user_data.voice_join_time = None

        self._save_data()

    @commands.command(name="xp")
    async def check_xp(self, ctx: commands.Context):
        user_data = self._get_user_data(ctx.author.id)
        tier = self._get_level_tier(user_data.level)

        embed = discord.Embed(
            title="XP Progress",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Level", value=str(user_data.level), inline=True)
        embed.add_field(name="Tier", value=tier, inline=True)
        embed.add_field(name="Total XP", value=str(user_data.total_xp), inline=True)
        embed.add_field(name="Message XP", value=str(user_data.message_xp), inline=True)
        embed.add_field(name="Voice XP", value=str(user_data.voice_xp), inline=True)
        embed.add_field(name="Messages Sent", value=str(user_data.message_count), inline=True)
        embed.add_field(name="Voice Hours", value=f"{user_data.voice_minutes // 60}h", inline=True)

        message_role = self._get_message_role(user_data.message_count)
        if message_role:
            embed.add_field(name="Message Tier", value=message_role, inline=True)

        voice_role = self._get_voice_role(user_data.voice_minutes)
        if voice_role:
            embed.add_field(name="Voice Tier", value=voice_role, inline=True)

        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="xpleaderboard")
    async def xp_leaderboard(self, ctx: commands.Context):
        sorted_users = sorted(
            self.user_data.items(),
            key=lambda x: x[1].total_xp,
            reverse=True,
        )[:10]

        embed = discord.Embed(title="XP Leaderboard", color=discord.Color.gold())

        for idx, (user_id, data) in enumerate(sorted_users, 1):
            try:
                user = await self.bot.fetch_user(int(user_id))
                name = user.name
            except:
                name = f"User {user_id}"

            embed.add_field(
                name=f"{idx}. {name}",
                value=f"Level {data.level} • {data.total_xp} XP",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(XPCog(bot))
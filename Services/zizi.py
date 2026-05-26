import discord
from discord.ext import commands, tasks
from discord.ui import View
from discord import app_commands
from datetime import timedelta
import asyncio
import random
from config import (
    DISCORD_TOKEN,
    OWNER_ID,
    GUILD_ID,
    MOD_ROLE_ID,
    VERIFIED_ROLE_NAME,
    CONFESSION_CHANNEL_ID,
    REMINDER_CHANNEL_ID,
    WELCOME_CHANNEL_ID,
    GOODBYE_CHANNEL_ID,
    HIGHLIGHTS_CHANNEL_ID,
)
from filter import FilterCog, banned_words
from hangman import HangmanCog
from fishgame import FishCog
from xpsystem import XPCog

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="?", intents=intents)

HIGHLIGHTS_REACTION_THRESHOLD = 2

roleplay_gifs = {
    "kiss":   "https://media.tenor.com/Tt72qF0Uk8sAAAAC/milk-and-mocha-bear.gif",
    "hug":    "https://media.tenor.com/vYg4u4xPIScAAAAC/milk-and-mocha.gif",
    "cuddle": "https://media.tenor.com/wCRu3cqJAgcAAAAC/milk-and-mocha-bear-love.gif",
    "love":   "https://media.tenor.com/_4YgA77ExHEAAAAC/milk-and-mocha-love.gif",
}

joke_list = [
    "Why don't skeletons fight each other? They don't have the guts.",
    "Why did the scarecrow win an award? Because he was outstanding in his field.",
    "Parallel lines have so much in common. It's a shame they'll never meet.",
]

roast_lines = [
    "You're the reason the gene pool needs a lifeguard.",
    "You're as useless as the 'ueue' in 'queue'.",
    "You're not stupid; you just have bad luck thinking.",
]

welcome_templates = [
    "Hey {mention}, welcome to **{guild}**!",
    "{mention} just arrived! Let's give them a warm welcome.",
    "A new star has joined us! Say hi to {mention}!",
]

goodbye_templates = [
    "{mention} has left the server...",
    "We just lost a star. Bye {name}!",
    "{name} said goodbye. We'll miss you.",
]


class VerificationView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_button")
    async def handle_verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
        if not verified_role:
            await interaction.response.send_message("Verification role not found.", ephemeral=True)
            return
        if verified_role in interaction.user.roles:
            await interaction.response.send_message("You are already verified!", ephemeral=True)
        else:
            await interaction.user.add_roles(verified_role)
            await interaction.response.send_message("You have been verified!", ephemeral=True)


def is_moderator(interaction: discord.Interaction) -> bool:
    return (
        interaction.user.id == OWNER_ID
        or discord.utils.get(interaction.user.roles, id=MOD_ROLE_ID) is not None
    )


@bot.event
async def on_ready():
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    bot.add_view(VerificationView())
    print(f"Logged in as {bot.user}")
    if not bump_reminder.is_running():
        bump_reminder.start()


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if any(word in message.content.lower() for word in banned_words):
        return

    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or not reaction.message.guild:
        return

    highlights_channel = bot.get_channel(HIGHLIGHTS_CHANNEL_ID)
    if not highlights_channel:
        return

    non_bot_reactors = [u async for u in reaction.users() if not u.bot]
    if len(non_bot_reactors) < HIGHLIGHTS_REACTION_THRESHOLD:
        return

    for existing_reaction in reaction.message.reactions:
        if str(existing_reaction.emoji) == "📸":
            return

    await reaction.message.add_reaction("📸")

    highlight_embed = discord.Embed(
        title="Message Highlighted!",
        description=reaction.message.content or "No text content",
        color=discord.Color.gold(),
    )
    highlight_embed.set_author(
        name=reaction.message.author.display_name,
        icon_url=reaction.message.author.avatar.url if reaction.message.author.avatar else None,
    )
    highlight_embed.add_field(name="Channel", value=reaction.message.channel.mention)
    highlight_embed.add_field(
        name="Jump to Message",
        value=f"[Click here]({reaction.message.jump_url})",
        inline=False,
    )
    if reaction.message.attachments:
        highlight_embed.set_image(url=reaction.message.attachments[0].url)
    highlight_embed.set_footer(text="Highlighted by the community")
    await highlights_channel.send(embed=highlight_embed)


@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return

    welcome_text = random.choice(welcome_templates).format(
        mention=member.mention,
        guild=member.guild.name,
    )
    human_member_count = len([m for m in member.guild.members if not m.bot])

    embed = discord.Embed(title="Welcome!", description=welcome_text, color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Joined At", value=discord.utils.format_dt(member.joined_at, style="F"), inline=True)
    embed.add_field(name="Member Count", value=str(human_member_count), inline=True)
    embed.set_footer(text=f"We're glad you're here, {member.name}!")
    await channel.send(embed=embed)


@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(GOODBYE_CHANNEL_ID)
    if not channel:
        return

    goodbye_text = random.choice(goodbye_templates).format(
        mention=member.mention,
        name=member.name,
    )
    human_member_count = len([m for m in member.guild.members if not m.bot])

    embed = discord.Embed(title="Someone Left...", description=goodbye_text, color=discord.Color.red())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="User", value=str(member), inline=True)
    embed.add_field(name="Remaining Members", value=str(human_member_count), inline=True)
    embed.set_footer(text="Hope they come back someday.")
    await channel.send(embed=embed)


@tasks.loop(minutes=30)
async def bump_reminder():
    channel = bot.get_channel(REMINDER_CHANNEL_ID)
    if channel:
        await channel.send("Don't forget to `/bump` the server!")


@bot.tree.command(name="confess", description="Send an anonymous confession")
@app_commands.describe(message="Your confession — no one will know it was you")
async def confess(interaction: discord.Interaction, message: str):
    confession_channel = bot.get_channel(CONFESSION_CHANNEL_ID)
    if confession_channel:
        embed = discord.Embed(title="Anonymous Confession", description=message, color=discord.Color.purple())
        await confession_channel.send(embed=embed)
    await interaction.response.send_message("Your confession was sent anonymously.", ephemeral=True)


@bot.tree.command(name="verifybutton", description="Post the verification button (owner only)")
async def verifybutton(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Only the server owner can use this.", ephemeral=True)
        return
    await interaction.channel.send("Click the button below to verify yourself!", view=VerificationView())
    await interaction.response.send_message("Verification button posted.", ephemeral=True)


@bot.tree.command(name="joke", description="Get a random joke")
async def joke(interaction: discord.Interaction):
    await interaction.response.send_message(random.choice(joke_list))


@bot.tree.command(name="bully", description="Roast a member (owner only)")
@app_commands.describe(member="The member to roast")
async def bully(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Only the server owner can use this.", ephemeral=True)
        return
    await interaction.response.send_message(f"{member.mention} {random.choice(roast_lines)}")


@bot.tree.command(name="purge", description="Delete messages in bulk (owner only)")
@app_commands.describe(amount="Number of messages to delete")
async def purge(interaction: discord.Interaction, amount: int):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Only the server owner can use this.", ephemeral=True)
        return
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"Deleted {len(deleted)} messages.", ephemeral=True)


ROLEPLAY_ACTIONS = {
    "kiss":   ("kissed",         "💋"),
    "hug":    ("hugged",         "🤗"),
    "cuddle": ("cuddled",        "🧸"),
    "love":   ("showed love to", "❤️"),
}


@bot.tree.command(name="roleplay", description="Send a roleplay action to another member")
@app_commands.describe(action="The action to perform", member="The target member")
@app_commands.choices(action=[
    app_commands.Choice(name="kiss",   value="kiss"),
    app_commands.Choice(name="hug",    value="hug"),
    app_commands.Choice(name="cuddle", value="cuddle"),
    app_commands.Choice(name="love",   value="love"),
])
async def roleplay(interaction: discord.Interaction, action: app_commands.Choice[str], member: discord.Member):
    verb, emoji = ROLEPLAY_ACTIONS[action.value]
    embed = discord.Embed().set_image(url=roleplay_gifs[action.value])
    await interaction.response.send_message(
        f"{interaction.user.mention} {verb} {member.mention}! {emoji}",
        embed=embed,
    )


@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="The member to kick", reason="Reason for the kick")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not is_moderator(interaction):
        await interaction.response.send_message("You don't have permission to kick members.", ephemeral=True)
        return
    await member.kick(reason=reason)
    await interaction.response.send_message(f"{member} was kicked. Reason: {reason}")


@bot.tree.command(name="ban", description="Permanently ban a member")
@app_commands.describe(member="The member to ban", reason="Reason for the ban")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not is_moderator(interaction):
        await interaction.response.send_message("You don't have permission to ban members.", ephemeral=True)
        return
    await member.ban(reason=reason)
    await interaction.response.send_message(f"{member} was banned. Reason: {reason}")


@bot.tree.command(name="timeout", description="Temporarily mute a member")
@app_commands.describe(member="The member to timeout", minutes="Duration in minutes", reason="Reason for the timeout")
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    if not is_moderator(interaction):
        await interaction.response.send_message("You don't have permission to timeout members.", ephemeral=True)
        return
    await member.timeout(timedelta(minutes=minutes), reason=reason)
    await interaction.response.send_message(f"{member} was timed out for {minutes} minutes. Reason: {reason}")


async def main():
    async with bot:
        await bot.add_cog(FilterCog(bot))
        await bot.add_cog(FishCog(bot))
        await bot.add_cog(HangmanCog(bot))
        await bot.add_cog(XPCog(bot))
        await bot.start(DISCORD_TOKEN)


asyncio.run(main())
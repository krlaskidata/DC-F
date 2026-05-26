import discord
import random
from discord.ext import commands
from discord import app_commands
from config import GAME_CHANNEL_ID

hangman_word_pool = [
    "python", "discord", "server", "keyboard", "monitor",
    "developer", "gaming", "stream", "message", "reaction",
    "moderator", "hangman", "confetti", "timeout", "community",
    "database", "network", "password", "channel", "website",
]


class HangmanGame:
    STAGES = [
        "```\n\n\n\n\n=====\n```",
        "```\n |\n |\n |\n |\n=====\n```",
        "```\n +---+\n |\n |\n |\n |\n=====\n```",
        "```\n +---+\n |   O\n |\n |\n |\n=====\n```",
        "```\n +---+\n |   O\n |   |\n |   |\n |\n=====\n```",
        "```\n +---+\n |   O\n |  /|\\\n |   |\n |\n=====\n```",
        "```\n +---+\n |   O\n |  /|\\\n |   |\n |  / \\\n=====\n```",
    ]

    def __init__(self, word):
        self.word = word
        self.guessed_letters = set()
        self.remaining_tries = 6

    def display_word(self):
        return " ".join(letter if letter in self.guessed_letters else "_" for letter in self.word)

    def guess_letter(self, letter):
        letter = letter.lower()
        if letter in self.guessed_letters:
            return False, "You already guessed that letter."
        self.guessed_letters.add(letter)
        if letter not in self.word:
            self.remaining_tries -= 1
            return False, f"Wrong guess. {self.remaining_tries} tries remaining."
        return True, "Correct!"

    def is_won(self):
        return all(letter in self.guessed_letters for letter in self.word)

    def is_lost(self):
        return self.remaining_tries <= 0

    def get_stage_art(self):
        return self.STAGES[6 - self.remaining_tries]


class HangmanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}

    @app_commands.command(name="hangman", description="Start a new Hangman game")
    async def hangman(self, interaction: discord.Interaction):
        if interaction.channel.id != GAME_CHANNEL_ID:
            await interaction.response.send_message(
                "Hangman can only be played in the designated game channel.", ephemeral=True
            )
            return

        chosen_word = random.choice(hangman_word_pool)
        game = HangmanGame(chosen_word)
        self.active_games[interaction.channel.id] = game

        embed = discord.Embed(title="Hangman — New Game", color=discord.Color.blurple())
        embed.description = (
            f"{game.get_stage_art()}\n"
            f"Word: `{game.display_word()}`\n"
            f"Tries remaining: {game.remaining_tries}\n"
            f"Use `/guess <letter>` to play."
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="guess", description="Guess a letter in the active Hangman game")
    @app_commands.describe(letter="The letter you want to guess")
    async def guess(self, interaction: discord.Interaction, letter: str):
        if interaction.channel.id != GAME_CHANNEL_ID:
            await interaction.response.send_message(
                "You can only play in the designated game channel.", ephemeral=True
            )
            return

        if interaction.channel.id not in self.active_games:
            await interaction.response.send_message(
                "No active Hangman game. Start one with `/hangman`.", ephemeral=True
            )
            return

        if len(letter) != 1 or not letter.isalpha():
            await interaction.response.send_message(
                "Please enter a single alphabetic letter.", ephemeral=True
            )
            return

        game = self.active_games[interaction.channel.id]
        _, result_message = game.guess_letter(letter)

        if game.is_won():
            embed = discord.Embed(title="You Won!", color=discord.Color.green())
            embed.description = f"Word: `{game.word}`\nYou guessed it correctly!"
            del self.active_games[interaction.channel.id]
        elif game.is_lost():
            embed = discord.Embed(title="Game Over", color=discord.Color.red())
            embed.description = f"{game.get_stage_art()}\nOut of tries. The word was: `{game.word}`"
            del self.active_games[interaction.channel.id]
        else:
            embed = discord.Embed(title="Hangman", color=discord.Color.orange())
            embed.description = (
                f"{game.get_stage_art()}\n"
                f"{result_message}\n\n"
                f"Word: `{game.display_word()}`\n"
                f"Tries remaining: {game.remaining_tries}"
            )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(HangmanCog(bot))
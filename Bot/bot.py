import discord
import json
from discord.ext import commands

with open('db/config.json') as fp:
    config = json.load(fp)

bot = commands.Bot(command_prefix=config["bot_prefix"])
bot.remove_command("help")

@bot.event
async def on_ready():
    for cog in config["cogs"]:
        bot.load_extension(cog)
    print('Ready!')

    
bot.run(config["bot_token"])

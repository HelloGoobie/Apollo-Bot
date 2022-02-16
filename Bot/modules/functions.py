import discord

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def embed_generator(bot, description, colour = 0x00FF00):
    embed = discord.Embed(description=description, colour=colour)
    embed.set_author(name=bot.user.name, icon_url= bot.user.avatar_url)
    return embed

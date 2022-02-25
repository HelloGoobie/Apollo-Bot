import discord

def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def embed_generator(bot, description, colour = 0x00FF00, author = None, avatar_url = None):
    if author is None:
        author = bot.user.name
    if avatar_url is None:
        avatar_url = bot.user.avatar_url
    embed = discord.Embed(description=description, colour=colour)
    embed.set_author(name=author, icon_url=avatar_url)
    return embed

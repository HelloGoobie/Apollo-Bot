import discord
from discord.ext import commands
import modules.functions as functions

class errors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            pass
        elif isinstance(error, (commands.MissingAnyRole, commands.MissingPermissions)):
            await ctx.reply(embed=functions.embed_generator(self.bot, "You are missing the permissions required to run this command", colour=0xFF0000))

        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(embed=functions.embed_generator(self.bot, "You are missing a required argument", colour=0xFF0000))
            
        else:
            raise error
        
def setup(bot):
    bot.add_cog(errors(bot))
